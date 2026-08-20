"""
TCP Server Engine
Accepts incoming file transfers and text snippets with on-the-fly decryption and decompression.
"""

import socket
import threading
import os
import sys
import time
import uuid
import hashlib
from app.config import TCP_PORT, WEB_PORT, SOCKET_BUFFER_SIZE, BUFFER_SIZE, state
from app.utils import safe_join, is_suspicious_file, format_bytes
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
                try:
                    client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SOCKET_BUFFER_SIZE)
                    client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCKET_BUFFER_SIZE)
                except Exception:
                    pass
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

            if msg_type == "PING":
                send_message(sock, {
                    "type": "PONG",
                    "name": state.device_name,
                    "port": self.port,
                    "web_port": WEB_PORT,
                    "timestamp": msg.get("timestamp"),
                    "ack": True
                })
                sock.close()
            elif msg_type == "TEXT_SNIPPET":
                self._handle_text_snippet(msg, sender_ip)
                sock.close()
            elif msg_type == "FILE_HEADER":
                self._handle_file_transfer(sock, msg, sender_ip)
            elif msg_type == "PARALLEL_FILE_HEADER":
                self._handle_parallel_file_header(sock, msg, sender_ip)
            elif msg_type == "PART_STREAM_HEADER":
                self._handle_part_stream(sock, msg, sender_ip)
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
            "transferred_bytes": resume_offset,
            "progress_percent": round((resume_offset / filesize * 100), 1) if filesize > 0 else 0.0,
            "direction": "INBOUND",
            "sender_ip": sender_ip,
            "status": "IN_PROGRESS",
            "encrypted": is_encrypted,
            "compressed": is_compressed,
            "start_time": time.time(),
            "end_time": 0.0,
            "speed": 0.0,
            "speed_mb": 0.0,
            "speed_mbps": 0.0,
            "eta": 0.0
        }
        state.transfers.insert(0, transfer_record)

        formatted_size = format_bytes(filesize)
        print(f"\n📥 [INCOMING] Receiving '{rel_path}' ({formatted_size}) from {sender_ip} "
              f"[Gzip: {is_compressed}, AES: {is_encrypted}]...")

        last_progress_print = [0.0]

        def _progress(received_bytes, total_bytes, metrics):
            transfer_record["received_bytes"] = received_bytes
            transfer_record["transferred_bytes"] = received_bytes
            transfer_record["speed"] = metrics.get("speed", 0.0)
            transfer_record["speed_mb"] = metrics.get("speed_mb", 0.0)
            transfer_record["speed_mbps"] = metrics.get("speed_mbps", 0.0)
            transfer_record["eta"] = metrics.get("eta", 0.0)
            transfer_record["progress_percent"] = metrics.get("percent", 0.0)

            # Live CLI output on receiver console
            now = time.time()
            if now - last_progress_print[0] >= 0.15 or received_bytes >= total_bytes:
                last_progress_print[0] = now
                pct = metrics.get("percent", 0.0)
                speed_mb = metrics.get("speed_mb", 0.0)
                speed_mbps = metrics.get("speed_mbps", 0.0)
                eta = metrics.get("eta", 0.0)
                eta_str = f"{eta:.1f}s" if eta > 0 else "0.0s"
                display_name = filename if len(filename) <= 18 else filename[:15] + "..."
                sys.stdout.write(
                    f"\r   📥 [Recv] {pct:5.1f}% | [{display_name:<18}] | "
                    f"Speed: {speed_mb:6.2f} MB/s ({speed_mbps:5.1f} Mbps) | ETA: {eta_str:<8}"
                )
                sys.stdout.flush()

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

        sys.stdout.write("\n")
        sys.stdout.flush()

        if ok:
            transfer_record["status"] = "COMPLETED"
            transfer_record["received_bytes"] = total_rec
            transfer_record["transferred_bytes"] = total_rec
            transfer_record["progress_percent"] = 100.0
            transfer_record["speed"] = 0.0
            transfer_record["speed_mb"] = 0.0
            transfer_record["speed_mbps"] = 0.0
            transfer_record["eta"] = 0.0
            transfer_record["end_time"] = time.time()
            elapsed_total = max(transfer_record["end_time"] - transfer_record["start_time"], 0.001)
            avg_speed_mb = (total_rec / elapsed_total) / (1024 * 1024)
            avg_speed_mbps = ((total_rec * 8) / elapsed_total) / (1024 * 1024)
            print(f"✅ Received successfully: {target_path} ({format_bytes(total_rec)} in {elapsed_total:.1f}s @ {avg_speed_mb:.2f} MB/s [{avg_speed_mbps:.1f} Mbps])\n")
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
            transfer_record["error_message"] = msg
            transfer_record["speed"] = 0.0
            transfer_record["speed_mb"] = 0.0
            transfer_record["speed_mbps"] = 0.0
            transfer_record["eta"] = 0.0
            transfer_record["end_time"] = time.time()
            print(f"❌ Transfer error for '{filename}': {msg}\n")
            send_message(sock, {
                "type": "TRANSFER_COMPLETE",
                "transfer_id": transfer_id,
                "status": "FAILED",
                "reason": msg
            })

        sock.close()

    def _handle_parallel_file_header(self, sock, header: dict, sender_ip: str):
        transfer_id = header.get("transfer_id", str(uuid.uuid4()))
        filename = header.get("filename", "received_file")
        rel_path = header.get("rel_path", filename)
        filesize = header.get("filesize", 0)
        num_parts = header.get("num_parts", 4)
        expected_checksum = header.get("checksum", "")

        # Security checks
        suspicious = is_suspicious_file(filename)
        if suspicious:
            print(f"⚠️ Warning: Incoming file '{filename}' has a potentially risky extension.")

        # Prepare target filepath securely
        os.makedirs(state.upload_dir, exist_ok=True)
        try:
            target_path = safe_join(state.upload_dir, rel_path)
        except ValueError:
            send_message(sock, {
                "type": "PARALLEL_FILE_RESPONSE",
                "transfer_id": transfer_id,
                "status": "REJECT",
                "reason": "Security path error."
            })
            sock.close()
            return

        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        try:
            fd = os.open(target_path, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o664)
            if filesize > 0:
                os.ftruncate(fd, filesize)
        except Exception as e:
            send_message(sock, {
                "type": "PARALLEL_FILE_RESPONSE",
                "transfer_id": transfer_id,
                "status": "REJECT",
                "reason": f"File creation error: {e}"
            })
            sock.close()
            return

        transfer_record = {
            "id": transfer_id,
            "filename": filename,
            "rel_path": rel_path,
            "filepath": target_path,
            "total_bytes": filesize,
            "received_bytes": 0,
            "transferred_bytes": 0,
            "progress_percent": 0.0,
            "direction": "INBOUND",
            "sender_ip": sender_ip,
            "status": "IN_PROGRESS",
            "encrypted": False,
            "compressed": False,
            "parallel_streams": num_parts,
            "start_time": time.time(),
            "end_time": 0.0,
            "speed": 0.0,
            "speed_mb": 0.0,
            "speed_mbps": 0.0,
            "eta": 0.0
        }
        state.transfers.insert(0, transfer_record)

        session = {
            "transfer_id": transfer_id,
            "fd": fd,
            "filename": filename,
            "filepath": target_path,
            "filesize": filesize,
            "num_parts": num_parts,
            "parts_done": set(),
            "bytes_received": 0,
            "start_time": time.time(),
            "event_all_done": threading.Event(),
            "lock": threading.Lock(),
            "transfer_record": transfer_record,
            "last_print": 0.0
        }
        state.active_parallel_sessions[transfer_id] = session

        formatted_size = format_bytes(filesize)
        print(f"\n📥 [INCOMING] Receiving '{rel_path}' ({formatted_size}) from {sender_ip} "
              f"[{num_parts}x Parallel Sockets]...")

        send_message(sock, {
            "type": "PARALLEL_FILE_RESPONSE",
            "transfer_id": transfer_id,
            "status": "ACCEPT",
            "num_parts": num_parts
        })

        # Wait for all worker streams to finish
        all_completed = session["event_all_done"].wait(timeout=3600.0)

        try:
            os.close(fd)
        except Exception:
            pass

        sys.stdout.write("\n")
        sys.stdout.flush()

        if all_completed and len(session["parts_done"]) == num_parts:
            transfer_record["status"] = "COMPLETED"
            transfer_record["received_bytes"] = filesize
            transfer_record["transferred_bytes"] = filesize
            transfer_record["progress_percent"] = 100.0
            transfer_record["speed"] = 0.0
            transfer_record["speed_mb"] = 0.0
            transfer_record["speed_mbps"] = 0.0
            transfer_record["eta"] = 0.0
            transfer_record["end_time"] = time.time()
            elapsed_total = max(transfer_record["end_time"] - transfer_record["start_time"], 0.001)
            avg_speed_mb = (filesize / elapsed_total) / (1024 * 1024)
            avg_speed_mbps = ((filesize * 8) / elapsed_total) / (1024 * 1024)
            print(f"✅ Received successfully: {target_path} ({format_bytes(filesize)} in {elapsed_total:.1f}s @ {avg_speed_mb:.2f} MB/s [{avg_speed_mbps:.1f} Mbps]) [{num_parts}x Sockets]\n")

            send_message(sock, {
                "type": "TRANSFER_COMPLETE",
                "transfer_id": transfer_id,
                "status": "SUCCESS",
                "received_bytes": filesize
            })
            record_transfer(transfer_record)
        else:
            transfer_record["status"] = "FAILED"
            transfer_record["error_message"] = "Parallel transfer timed out or stream broke"
            transfer_record["end_time"] = time.time()
            print(f"❌ Transfer error for '{filename}': Parallel streams did not complete in time.\n")
            send_message(sock, {
                "type": "TRANSFER_COMPLETE",
                "transfer_id": transfer_id,
                "status": "FAILED",
                "reason": "Parallel stream failure"
            })

        state.active_parallel_sessions.pop(transfer_id, None)
        processor.reset_metrics_window(transfer_id)
        sock.close()

    def _handle_part_stream(self, sock, header: dict, sender_ip: str):
        transfer_id = header.get("transfer_id")
        part_index = header.get("part_index", 0)
        offset = header.get("offset", 0)
        length = header.get("length", 0)

        session = state.active_parallel_sessions.get(transfer_id)
        if not session:
            send_message(sock, {"type": "PART_RESPONSE", "status": "ERROR", "reason": "No active session"})
            sock.close()
            return

        send_message(sock, {"type": "PART_RESPONSE", "status": "READY", "part_index": part_index})

        fd = session["fd"]
        current_offset = offset
        remaining = length

        try:
            while remaining > 0:
                chunk_to_read = min(BUFFER_SIZE, remaining)
                chunk = sock.recv(chunk_to_read)
                if not chunk:
                    break
                
                # Atomic zero-lock write at file offset
                os.pwrite(fd, chunk, current_offset)
                chunk_len = len(chunk)
                current_offset += chunk_len
                remaining -= chunk_len

                with session["lock"]:
                    session["bytes_received"] += chunk_len
                    total_rec = session["bytes_received"]
                    rec = session["transfer_record"]
                    now = time.time()
                    
                    if now - session["last_print"] >= 0.1 or total_rec >= session["filesize"]:
                        session["last_print"] = now
                        metrics = processor.calculate_metrics(
                            transferred_bytes=total_rec,
                            total_bytes=session["filesize"],
                            start_time=session["start_time"],
                            transfer_id=transfer_id
                        )
                        rec["received_bytes"] = total_rec
                        rec["transferred_bytes"] = total_rec
                        rec["speed"] = metrics.get("speed", 0.0)
                        rec["speed_mb"] = metrics.get("speed_mb", 0.0)
                        rec["speed_mbps"] = metrics.get("speed_mbps", 0.0)
                        rec["eta"] = metrics.get("eta", 0.0)
                        rec["progress_percent"] = metrics.get("percent", 0.0)

                        pct = metrics.get("percent", 0.0)
                        speed_mb = metrics.get("speed_mb", 0.0)
                        speed_mbps = metrics.get("speed_mbps", 0.0)
                        eta = metrics.get("eta", 0.0)
                        eta_str = f"{eta:.1f}s" if eta > 0 else "0.0s"
                        fname = session["filename"] if len(session["filename"]) <= 16 else session["filename"][:13] + "..."
                        sys.stdout.write(
                            f"\r   📥 [Recv {session['num_parts']}x] {pct:5.1f}% | [{fname:<16}] | "
                            f"Speed: {speed_mb:6.2f} MB/s ({speed_mbps:5.1f} Mbps) | ETA: {eta_str:<8}"
                        )
                        sys.stdout.flush()

            if remaining == 0:
                with session["lock"]:
                    session["parts_done"].add(part_index)
                    if len(session["parts_done"]) == session["num_parts"]:
                        session["event_all_done"].set()

        except Exception as e:
            print(f"\n⚠️ Error in stream part {part_index}: {e}")
        finally:
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
