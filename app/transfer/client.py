"""
TCP Client Engine
Handles outbound file transfers, multi-folder batch transmission, Gzip compression, and AES-256-GCM encryption.
"""

import socket
import os
import time
import uuid
from app.config import TCP_PORT, SOCKET_BUFFER_SIZE, state
from app.utils import is_compressible_file, compute_file_hash
from app.transfer.protocol import send_message, receive_message
from app.processing.engine import processor
from app.security.encryption import encrypt_text
from app.queue.models import TransferTask, BatchTransferTask, TransferStatus
from app.queue.manager import queue_manager
from app.db.mongo import record_transfer

def send_text_snippet(
    target_ip: str,
    text: str,
    target_port: int = TCP_PORT,
    sender_name: str = None,
    encrypt: bool = None
) -> tuple[bool, str]:
    """Send an encrypted or plain text snippet to target IP."""
    use_encryption = state.encryption_enabled if encrypt is None else encrypt
    payload_text = text

    if use_encryption and state.encryption_key:
        try:
            payload_text = encrypt_text(text, state.encryption_key)
        except Exception as e:
            return False, f"Encryption failed: {e}"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    try:
        sock.connect((target_ip, target_port))
        send_message(sock, {
            "type": "TEXT_SNIPPET",
            "text": payload_text,
            "sender": sender_name or state.device_name,
            "is_encrypted": use_encryption,
            "timestamp": time.time()
        })
        return True, "Snippet sent successfully."
    except Exception as e:
        return False, f"Failed to send snippet: {e}"
    finally:
        sock.close()

def send_single_file(
    target_ip: str,
    file_path: str,
    rel_path: str = None,
    target_port: int = TCP_PORT,
    progress_callback = None
) -> tuple[bool, str]:
    """Send a single file with streaming Gzip compression and AES-GCM encryption."""
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}"

    filename = os.path.basename(file_path)
    relative_name = rel_path or filename
    filesize = os.path.getsize(file_path)
    transfer_id = str(uuid.uuid4())

    use_compression = state.compression_enabled and is_compressible_file(filename) and filesize > 1024
    use_encryption = state.encryption_enabled and bool(state.encryption_key)
    file_checksum = compute_file_hash(file_path)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SOCKET_BUFFER_SIZE)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCKET_BUFFER_SIZE)
    except Exception:
        pass
    sock.settimeout(30.0)

    # Register active outbound transfer record in state
    transfer_record = {
        "id": transfer_id,
        "filename": filename,
        "rel_path": relative_name,
        "filepath": file_path,
        "total_bytes": filesize,
        "received_bytes": 0,
        "transferred_bytes": 0,
        "progress_percent": 0.0,
        "direction": "OUTBOUND",
        "target_ip": target_ip,
        "status": "IN_PROGRESS",
        "encrypted": use_encryption,
        "compressed": use_compression,
        "speed": 0.0,
        "speed_mb": 0.0,
        "speed_mbps": 0.0,
        "eta": 0.0,
        "start_time": time.time(),
        "end_time": 0.0
    }
    state.transfers.insert(0, transfer_record)

    def _wrapped_progress(sent_bytes, total_bytes, metrics):
        transfer_record["transferred_bytes"] = sent_bytes
        transfer_record["received_bytes"] = sent_bytes
        transfer_record["progress_percent"] = metrics.get("percent", 0.0)
        transfer_record["speed"] = metrics.get("speed", 0.0)
        transfer_record["speed_mb"] = metrics.get("speed_mb", 0.0)
        transfer_record["speed_mbps"] = metrics.get("speed_mbps", 0.0)
        transfer_record["eta"] = metrics.get("eta", 0.0)
        if progress_callback:
            progress_callback(sent_bytes, total_bytes, metrics)

    try:
        sock.connect((target_ip, target_port))
        
        # Send FILE_HEADER
        send_message(sock, {
            "type": "FILE_HEADER",
            "transfer_id": transfer_id,
            "filename": filename,
            "rel_path": relative_name,
            "filesize": filesize,
            "is_compressed": use_compression,
            "is_encrypted": use_encryption,
            "checksum": file_checksum
        })

        # Wait for server response
        response = receive_message(sock)
        if not response or response.get("type") != "FILE_RESPONSE":
            transfer_record["status"] = "FAILED"
            transfer_record["error_message"] = "No response from receiving peer."
            return False, "No response from receiving peer."

        status = response.get("status")
        if status != "ACCEPT":
            reason = response.get("reason", "Declined")
            transfer_record["status"] = "FAILED"
            transfer_record["error_message"] = f"Peer rejected transfer: {reason}"
            return False, f"Peer rejected transfer: {reason}"

        resume_offset = response.get("resume_offset", 0)

        # Stream file data through processor
        ok, msg = processor.process_and_send_file(
            sock=sock,
            file_path=file_path,
            filesize=filesize,
            use_compression=use_compression,
            use_encryption=use_encryption,
            encryption_key=state.encryption_key,
            resume_offset=resume_offset,
            progress_callback=_wrapped_progress
        )

        if not ok:
            transfer_record["status"] = "FAILED"
            transfer_record["error_message"] = msg
            return False, msg

        # Wait for final ACK
        final_ack = receive_message(sock)
        if final_ack and final_ack.get("status") == "SUCCESS":
            transfer_record["status"] = "COMPLETED"
            transfer_record["transferred_bytes"] = filesize
            transfer_record["received_bytes"] = filesize
            transfer_record["progress_percent"] = 100.0
            transfer_record["speed"] = 0.0
            transfer_record["speed_mb"] = 0.0
            transfer_record["speed_mbps"] = 0.0
            transfer_record["eta"] = 0.0
            transfer_record["end_time"] = time.time()
            
            # Record outbound transfer in MongoDB
            record_transfer({
                "id": transfer_id,
                "filename": filename,
                "rel_path": relative_name,
                "filepath": file_path,
                "total_bytes": filesize,
                "direction": "OUTBOUND",
                "target_ip": target_ip,
                "status": "COMPLETED",
                "encrypted": use_encryption,
                "compressed": use_compression
            })
            return True, "File transferred and verified successfully."
        elif final_ack and final_ack.get("status") == "FAILED":
            err = final_ack.get('reason', 'Unknown error')
            transfer_record["status"] = "FAILED"
            transfer_record["error_message"] = f"Peer error: {err}"
            return False, f"Peer error: {err}"

        transfer_record["status"] = "COMPLETED"
        transfer_record["progress_percent"] = 100.0
        transfer_record["end_time"] = time.time()
        return True, "File stream completed."
    except Exception as e:
        transfer_record["status"] = "FAILED"
        transfer_record["error_message"] = f"Socket error: {e}"
        return False, f"Socket error: {e}"
    finally:
        sock.close()

def send_batch(
    target_ip: str,
    batch: BatchTransferTask,
    target_port: int = TCP_PORT,
    batch_progress_callback = None
) -> tuple[int, int]:
    """Send all tasks in a batch sequentially."""
    success_count = 0
    total_count = len(batch.tasks)

    for task in batch.tasks:
        if batch.status == TransferStatus.CANCELLED:
            break

        task.status = TransferStatus.IN_PROGRESS
        task.start_time = time.time()

        def _task_progress(sent_bytes, total_bytes, metrics):
            task.transferred_bytes = sent_bytes
            task.speed = metrics["speed"]
            task.eta = metrics["eta"]
            batch.update_aggregate_metrics()
            if batch_progress_callback:
                batch_progress_callback(batch, task, metrics)

        ok, msg = send_single_file(
            target_ip=target_ip,
            file_path=task.local_path,
            rel_path=task.relative_path,
            target_port=target_port,
            progress_callback=_task_progress
        )

        if ok:
            task.status = TransferStatus.COMPLETED
            task.transferred_bytes = task.filesize
            task.speed = 0.0
            task.eta = 0.0
            success_count += 1
        else:
            task.status = TransferStatus.FAILED
            task.error_message = msg
            task.speed = 0.0
            task.eta = 0.0

        task.end_time = time.time()
        batch.update_aggregate_metrics()

    return success_count, total_count

# Hook queue manager task executor
def _execute_queue_task(task: TransferTask):
    def _cb(sent_bytes, total_bytes, metrics):
        task.transferred_bytes = sent_bytes
        task.speed = metrics.get("speed", 0.0)
        task.eta = metrics.get("eta", 0.0)
        if task.batch_id:
            batch = queue_manager.get_batch(task.batch_id)
            if batch:
                batch.update_aggregate_metrics()

    ok, msg = send_single_file(
        target_ip=task.target_ip,
        file_path=task.local_path,
        rel_path=task.relative_path,
        progress_callback=_cb
    )
    if ok:
        task.status = TransferStatus.COMPLETED
        task.transferred_bytes = task.filesize
        task.speed = 0.0
        task.eta = 0.0
    else:
        task.status = TransferStatus.FAILED
        task.error_message = msg
        task.speed = 0.0
        task.eta = 0.0

    if task.batch_id:
        batch = queue_manager.get_batch(task.batch_id)
        if batch:
            batch.update_aggregate_metrics()

queue_manager.set_execution_handler(_execute_queue_task)
