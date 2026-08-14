"""
TCP Server Engine
Accepts incoming file transfers and text snippets with on-the-fly decryption and decompression.
"""

import socket
import threading
import os
import time
import uuid
from app.config import TCP_PORT, state
from app.utils import safe_join, is_suspicious_file
from app.transfer.protocol import send_message, receive_message
from app.processing.engine import processor
from app.security.encryption import decrypt_text
from app.db.mongo import record_transfer, save_clipboard_item

_server_instance = None

class TCPServer:
    """TCP Server socket listener."""

    def __init__(self, port=TCP_PORT):
        self.port = port
        self.running = False
        self.server_socket = None

    def start(self):
        """Start listening for incoming TCP transfers in a daemon background thread."""
        if self.running:
            return
        self.running = True
        
        bound = False
        attempts = 0
        while not bound and attempts < 10:
            current_port = self.port + attempts
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.server_socket.bind(("0.0.0.0", current_port))
                self.server_socket.listen(15)
                self.port = current_port
                bound = True
            except OSError:
                self.server_socket.close()
                attempts += 1

        if not bound:
            print(f"❌ Failed to bind TCP server on ports {self.port} - {self.port + 9}")
            self.running = False
            return

        self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.accept_thread.start()
        print(f"📁 TCP Mesh Engine listening on port {self.port}")

    def stop(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            try:
                dummy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                dummy.settimeout(0.1)
                dummy.connect(("127.0.0.1", self.port))
                dummy.close()
            except Exception:
                pass

    def _accept_loop(self):
        while self.running:
            try:
                self.server_socket.settimeout(2.0)
                client_sock, client_addr = self.server_socket.accept()
            except socket.timeout:
                continue
            except Exception:
                break

            client_thread = threading.Thread(
                target=self._handle_client,
                args=(client_sock, client_addr),
                daemon=True
            )
            client_thread.start()

    def _handle_client(self, sock, addr):
        sender_ip = addr[0]
        try:
            msg = receive_message(sock)
            if not msg:
                sock.close()
                return

            msg_type = msg.get("type")

            if msg_type == "TEXT_SNIPPET":
                self._handle_text_snippet(msg, sender_ip)
                sock.close()
            elif msg_type == "FILE_HEADER":
                self._handle_file_transfer(sock, msg, sender_ip)
            else:
                sock.close()

        except Exception:
            try:
                sock.close()
            except Exception:
                pass

    def _handle_text_snippet(self, msg: dict, sender_ip: str):
        text = msg.get("text", "")
        sender = msg.get("sender", sender_ip)
        is_encrypted = msg.get("is_encrypted", False)
        timestamp = msg.get("timestamp", time.time())

        if is_encrypted and state.encryption_key:
            try:
                text = decrypt_text(text, state.encryption_key)
            except Exception as e:
                print(f"⚠️ Decryption failed for text snippet from {sender_ip}: {e}")
                return

        snippet_record = {
            "id": str(uuid.uuid4()),
            "text": text,
            "sender": sender,
            "sender_ip": sender_ip,
            "encrypted": is_encrypted,
            "timestamp": timestamp
        }
        
        state.clipboard_history.insert(0, snippet_record)
        if len(state.clipboard_history) > 50:
            state.clipboard_history.pop()

        # Save to MongoDB
        save_clipboard_item(text, sender=sender, sender_ip=sender_ip)

        # Set system clipboard
        try:
            from app.sync.clipboard import set_system_clipboard
            set_system_clipboard(text)
        except Exception:
            pass

        print(f"\n📋 Received Snippet from {sender} ({sender_ip}) [{'ENCRYPTED' if is_encrypted else 'PLAIN'}]:")
        print(f"   \"{text[:100]}{'...' if len(text) > 100 else ''}\"")

    def _handle_file_transfer(self, sock, header: dict, sender_ip: str):
        transfer_id = header.get("transfer_id", str(uuid.uuid4()))
        filename = header.get("filename", "received_file")
        rel_path = header.get("rel_path", filename)
        filesize = header.get("filesize", 0)
        is_compressed = header.get("is_compressed", False)
        is_encrypted = header.get("is_encrypted", False)
        expected_checksum = header.get("checksum", "")
        
        suspicious = is_suspicious_file(filename)
        if suspicious:
            print(f"⚠️ Warning: Incoming file '{filename}' has a potentially risky extension.")

        # Check approval requirement
        if not state.auto_approve:
            approval_event = threading.Event()
            state.pending_approvals[transfer_id] = {
                "transfer_id": transfer_id,
                "filename": filename,
                "rel_path": rel_path,
                "filesize": filesize,
                "sender_ip": sender_ip,
                "suspicious": suspicious,
                "event": approval_event,
                "status": "PENDING"
            }
            
            print(f"\n🔔 APPROVAL REQUIRED: Accept '{filename}' ({filesize} bytes) from {sender_ip}? (Y/n)")
            approved = approval_event.wait(timeout=30.0)
            status = state.pending_approvals.get(transfer_id, {}).get("status", "REJECT")
            state.pending_approvals.pop(transfer_id, None)

            if not approved or status != "ACCEPT":
                send_message(sock, {
                    "type": "FILE_RESPONSE",
                    "transfer_id": transfer_id,
                    "status": "REJECT",
                    "reason": "Transfer declined by receiver."
                })
                sock.close()
                return

        # Prepare target filepath securely
        os.makedirs(state.upload_dir, exist_ok=True)
        try:
            target_path = safe_join(state.upload_dir, rel_path)
        except ValueError:
            send_message(sock, {
                "type": "FILE_RESPONSE",
                "transfer_id": transfer_id,
                "status": "REJECT",
                "reason": "Security path error."
            })
            sock.close()
            return

        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        # Check for existing partial file for RESUME
        resume_offset = 0
        if os.path.exists(target_path) and not is_encrypted and not is_compressed:
            existing_size = os.path.getsize(target_path)
            if 0 < existing_size < filesize:
                resume_offset = existing_size

        # Send response header
        send_message(sock, {
            "type": "FILE_RESPONSE",
            "transfer_id": transfer_id,
            "status": "ACCEPT",
            "resume_offset": resume_offset
        })

        # Register active transfer record in state
        transfer_record = {
            "id": transfer_id,
            "filename": filename,
            "rel_path": rel_path,
            "filepath": target_path,
            "total_bytes": filesize,
            "received_bytes": resume_offset,
            "sender_ip": sender_ip,
            "status": "IN_PROGRESS",
            "encrypted": is_encrypted,
            "compressed": is_compressed,
            "start_time": time.time(),
            "speed": 0
        }
        state.transfers.insert(0, transfer_record)

        print(f"📥 Receiving '{rel_path}' ({filesize} bytes) from {sender_ip} "
              f"[Gzip: {is_compressed}, AES: {is_encrypted}]...")

        def _progress(received_bytes, total_bytes, metrics):
            transfer_record["received_bytes"] = received_bytes
            transfer_record["speed"] = metrics["speed"]

        ok, msg, total_rec = processor.receive_and_save_file(
            sock=sock,
            target_path=target_path,
            filesize=filesize,
            is_compressed=is_compressed,
            is_encrypted=is_encrypted,
            encryption_key=state.encryption_key,
            resume_offset=resume_offset,
            expected_checksum=expected_checksum,
            progress_callback=_progress
        )

        if ok:
            transfer_record["status"] = "COMPLETED"
            transfer_record["received_bytes"] = total_rec
            print(f"✅ Received successfully: {target_path}")
            send_message(sock, {
                "type": "TRANSFER_COMPLETE",
                "transfer_id": transfer_id,
                "status": "SUCCESS",
                "received_bytes": total_rec
            })
            # Persist to MongoDB
            record_transfer(transfer_record)
        else:
            transfer_record["status"] = "FAILED"
            print(f"❌ Transfer error for '{filename}': {msg}")
            send_message(sock, {
                "type": "TRANSFER_COMPLETE",
                "transfer_id": transfer_id,
                "status": "FAILED",
                "reason": msg
            })

        sock.close()

def start_tcp_server(port=TCP_PORT) -> TCPServer:
    """Start global TCP server engine."""
    global _server_instance
    if _server_instance is None:
        _server_instance = TCPServer(port=port)
        _server_instance.start()
    return _server_instance

def stop_tcp_server():
    """Stop global TCP server engine."""
    global _server_instance
    if _server_instance is not None:
        _server_instance.stop()
        _server_instance = None
