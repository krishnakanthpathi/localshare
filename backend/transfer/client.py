"""
TCP File & Snippet Client Engine
Handles outbound file transfers, directory preservation, compression, and text sync.
"""

import socket
import os
import gzip
import time
import uuid
import threading
try:
    from config import TCP_PORT, BUFFER_SIZE, PARALLEL_STREAMS_THRESHOLD, PARALLEL_STREAMS_COUNT
    from utils import is_compressible_file, compute_file_hash
except ImportError:
    from ..config import TCP_PORT, BUFFER_SIZE, PARALLEL_STREAMS_THRESHOLD, PARALLEL_STREAMS_COUNT
    from ..utils import is_compressible_file, compute_file_hash
from .protocol import send_message, receive_message

class TCPClientEngine:
    @staticmethod
    def send_text_snippet(target_ip, text, target_port=TCP_PORT, sender_name=None):
        """Send a text snippet or clipboard item to a target device."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        try:
            sock.connect((target_ip, target_port))
            send_message(sock, {
                "type": "TEXT_SNIPPET",
                "text": text,
                "sender": sender_name or socket.gethostname(),
                "timestamp": time.time()
            })
            return True, "Snippet sent successfully."
        except Exception as e:
            return False, f"Failed to send snippet: {e}"
        finally:
            sock.close()

    @staticmethod
    def send_path(target_ip, local_path, target_port=TCP_PORT, progress_callback=None):
        """
        Send a single file OR an entire directory tree recursively to target device.
        """
        if not os.path.exists(local_path):
            return False, f"File path does not exist: {local_path}"

        if os.path.isfile(local_path):
            filename = os.path.basename(local_path)
            return TCPClientEngine._send_single_file(target_ip, target_port, local_path, filename, progress_callback)
        elif os.path.isdir(local_path):
            # Scan directory tree
            folder_name = os.path.basename(os.path.normpath(local_path))
            files_to_send = []
            
            for root, dirs, files in os.walk(local_path):
                for file in files:
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, start=os.path.dirname(local_path))
                    files_to_send.append((full_p, rel_p))

            if not files_to_send:
                return False, "Directory is empty."

            print(f"📁 Batch sending directory '{folder_name}' ({len(files_to_send)} files)...")
            success_count = 0

            for full_p, rel_p in files_to_send:
                ok, err = TCPClientEngine._send_single_file(target_ip, target_port, full_p, rel_p, progress_callback)
                if ok:
                    success_count += 1
                else:
                    print(f"⚠️ Warning: Failed to send {rel_p}: {err}")

            return success_count > 0, f"Transferred {success_count}/{len(files_to_send)} files."

        return False, "Invalid path type."

    @staticmethod
    def _send_single_file(target_ip, target_port, file_path, rel_path, progress_callback=None):
        """Send a single file with optional compression and resume support."""
        if not os.path.exists(file_path):
            return False, "File does not exist."

        filename = os.path.basename(file_path)
        raw_size = os.path.getsize(file_path)
        transfer_id = str(uuid.uuid4())
        
        # Check compression candidate
        use_compression = is_compressible_file(filename) and raw_size > 1024
        
        print(f"📤 Connecting to {target_ip}:{target_port} for '{rel_path}'...")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30.0)

        try:
            sock.connect((target_ip, target_port))
            
            # Send FILE_HEADER
            send_message(sock, {
                "type": "FILE_HEADER",
                "transfer_id": transfer_id,
                "filename": filename,
                "rel_path": rel_path,
                "filesize": raw_size,
                "is_compressed": use_compression,
                "checksum": compute_file_hash(file_path)
            })

            # Wait for server response
            response = receive_message(sock)
            if not response or response.get("type") != "FILE_RESPONSE":
                return False, "No valid response from server."

            status = response.get("status")
            if status != "ACCEPT":
                reason = response.get("reason", "Declined")
                return False, f"Server rejected file: {reason}"

            resume_offset = response.get("resume_offset", 0)

            print(f"🚀 Transferring '{rel_path}' ({raw_size} bytes, Compressed: {use_compression}, Resume offset: {resume_offset})...")

            sent_bytes = resume_offset
            start_time = time.time()

            with open(file_path, "rb") as f:
                if resume_offset > 0:
                    f.seek(resume_offset)

                if use_compression:
                    # Gzip compression stream
                    gz_obj = gzip.GzipFile(mode="wb", fileobj=sock_writer_wrapper(sock))
                    while sent_bytes < raw_size:
                        chunk = f.read(BUFFER_SIZE)
                        if not chunk:
                            break
                        gz_obj.write(chunk)
                        sent_bytes += len(chunk)
                        
                        elapsed = max(time.time() - start_time, 0.001)
                        speed = (sent_bytes - resume_offset) / elapsed
                        if progress_callback:
                            progress_callback(rel_path, sent_bytes, raw_size, speed)
                    gz_obj.close()
                else:
                    # Raw binary stream
                    while sent_bytes < raw_size:
                        chunk = f.read(BUFFER_SIZE)
                        if not chunk:
                            break
                        sock.sendall(chunk)
                        sent_bytes += len(chunk)

                        elapsed = max(time.time() - start_time, 0.001)
                        speed = (sent_bytes - resume_offset) / elapsed
                        if progress_callback:
                            progress_callback(rel_path, sent_bytes, raw_size, speed)

            # Wait for final server confirmation ACK
            final_ack = receive_message(sock)
            if final_ack and final_ack.get("status") == "SUCCESS":
                return True, "File transferred successfully."
            return True, "File sent (awaiting ack)."

        except Exception as e:
            return False, f"Socket error: {e}"
        finally:
            sock.close()

class sock_writer_wrapper:
    """Wrapper to make socket look like a write-only file object for gzip.GzipFile."""
    def __init__(self, sock):
        self.sock = sock
    def write(self, data):
        self.sock.sendall(data)
        return len(data)
    def flush(self):
        pass
