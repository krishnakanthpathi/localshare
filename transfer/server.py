"""
TCP File & Snippet Server Engine
Listens on TCP_PORT (4000), manages incoming transfers, resumable offsets, and user approvals.
"""

import socket
import threading
import os
import gzip
import time
import uuid
from ..config import TCP_PORT, BUFFER_SIZE, state
from ..utils import safe_join, is_suspicious_file
from .protocol import send_message, receive_message

class TCPServerEngine:
    def __init__(self, port=TCP_PORT):
        self.port = port
        self.running = False
        self.server_socket = None

    def start(self):
        """Start listening for incoming TCP transfers in a daemon thread."""
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
                self.server_socket.listen(10)
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
        print(f"📁 TCP File Server active on port {self.port}")

    def stop(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            # Trigger dummy connect to wake up accept loop if needed
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

    def _handle_text_snippet(self, msg, sender_ip):
        text = msg.get("text", "")
        sender = msg.get("sender", sender_ip)
        timestamp = msg.get("timestamp", time.time())

        snippet_record = {
            "id": str(uuid.uuid4()),
            "text": text,
            "sender": sender,
            "sender_ip": sender_ip,
            "timestamp": timestamp
        }
        
        state.clipboard_history.insert(0, snippet_record)
        # Limit history to 50
        if len(state.clipboard_history) > 50:
            state.clipboard_history.pop()

        print(f"\n📋 Received Text Snippet from {sender} ({sender_ip}):")
        print(f"   \"{text[:100]}{'...' if len(text) > 100 else ''}\"")

    def _handle_file_transfer(self, sock, header, sender_ip):
        transfer_id = header.get("transfer_id", str(uuid.uuid4()))
        filename = header.get("filename", "received_file")
        rel_path = header.get("rel_path", filename)
        filesize = header.get("filesize", 0)
        is_compressed = header.get("is_compressed", False)
        
        # Check suspicious file
        suspicious = is_suspicious_file(filename)
        if suspicious:
            print(f"⚠️ Warning: Incoming file '{filename}' has a potentially executable extension.")

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
            
            # Wait up to 30 seconds for user action via CLI or Web UI
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
        if os.path.exists(target_path):
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
            "start_time": time.time(),
            "speed": 0
        }
        state.transfers.insert(0, transfer_record)

        print(f"📥 Receiving '{rel_path}' ({filesize} bytes) from {sender_ip} (Resuming from {resume_offset} bytes)...")

        try:
            mode = "ab" if resume_offset > 0 else "wb"
            received_total = resume_offset
            start_t = time.time()

            with open(target_path, mode) as f:
                if is_compressed:
                    # Decompress stream
                    decompressor = gzip.GzipFile(fileobj=sock_stream_wrapper(sock), mode="rb")
                    while received_total < filesize:
                        chunk = decompressor.read(BUFFER_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        received_total += len(chunk)
                        transfer_record["received_bytes"] = received_total
                        elapsed = max(time.time() - start_t, 0.001)
                        transfer_record["speed"] = (received_total - resume_offset) / elapsed
                else:
                    # Raw socket stream
                    while received_total < filesize:
                        chunk_size = min(BUFFER_SIZE, filesize - received_total)
                        chunk = sock.recv(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        received_total += len(chunk)
                        transfer_record["received_bytes"] = received_total
                        elapsed = max(time.time() - start_t, 0.001)
                        transfer_record["speed"] = (received_total - resume_offset) / elapsed

            transfer_record["status"] = "COMPLETED"
            print(f"\n✅ Received successfully: {target_path}")

            # Send final confirmation ACK
            send_message(sock, {
                "type": "TRANSFER_COMPLETE",
                "transfer_id": transfer_id,
                "status": "SUCCESS",
                "received_bytes": received_total
            })

        except Exception as e:
            transfer_record["status"] = "FAILED"
            print(f"\n❌ Transfer error for '{filename}': {e}")
        finally:
            sock.close()

class sock_stream_wrapper:
    """Wrapper to make a socket look like a read-only file object for gzip.GzipFile."""
    def __init__(self, sock):
        self.sock = sock
    def read(self, size=-1):
        try:
            return self.sock.recv(size if size > 0 else BUFFER_SIZE)
        except Exception:
            return b""
