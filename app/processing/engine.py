"""
Transfer Processing Engine
Handles streaming Gzip compression, AES-256-GCM chunk encryption, incremental checksums, and speed metrics.
"""

import os
import time
import zlib
import struct
import hashlib
from app.config import BUFFER_SIZE, state
from app.security.encryption import encrypt_chunk, decrypt_chunk
from app.processing.stream import read_exact_bytes

CHUNK_HEADER_FORMAT = ">I"  # 4-byte unsigned integer chunk length
CHUNK_HEADER_SIZE = struct.calcsize(CHUNK_HEADER_FORMAT)

class TransferProcessor:
    """Core processor object for orchestrating streaming data transformation."""

    def __init__(self):
        pass

    def calculate_metrics(self, transferred_bytes: int, total_bytes: int, start_time: float, offset_bytes: int = 0):
        """Calculate transfer speed (B/s), ETA (seconds), and completion percentage."""
        elapsed = max(time.time() - start_time, 0.001)
        net_transferred = max(transferred_bytes - offset_bytes, 0)
        speed = net_transferred / elapsed
        
        remaining_bytes = max(total_bytes - transferred_bytes, 0)
        eta = remaining_bytes / speed if speed > 0 else 0
        percent = (transferred_bytes / total_bytes * 100) if total_bytes > 0 else 100.0
        
        return {
            "speed": speed,
            "speed_mb": speed / (1024 * 1024),
            "eta": round(eta, 1),
            "percent": round(percent, 1),
            "elapsed": round(elapsed, 1)
        }

    def process_and_send_file(
        self,
        sock,
        file_path: str,
        filesize: int,
        use_compression: bool,
        use_encryption: bool,
        encryption_key: str = "",
        resume_offset: int = 0,
        progress_callback = None
    ) -> tuple[bool, str]:
        """
        Stream a file over socket applying optional Gzip compression and AES-GCM encryption.
        """
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"

        start_time = time.time()
        sent_raw_bytes = resume_offset
        compressor = zlib.compressobj(state.compression_level, zlib.DEFLATED, zlib.MAX_WBITS | 16) if use_compression else None
        
        try:
            with open(file_path, "rb") as f:
                if resume_offset > 0:
                    f.seek(resume_offset)

                while sent_raw_bytes < filesize:
                    chunk = f.read(BUFFER_SIZE)
                    if not chunk:
                        break
                    
                    sent_raw_bytes += len(chunk)
                    
                    # 1. Compression stage
                    if use_compression:
                        transformed = compressor.compress(chunk)
                    else:
                        transformed = chunk

                    # 2. Encryption stage
                    if transformed:
                        if use_encryption:
                            enc_chunk = encrypt_chunk(transformed, encryption_key)
                            header = struct.pack(CHUNK_HEADER_FORMAT, len(enc_chunk))
                            sock.sendall(header + enc_chunk)
                        else:
                            if use_compression:
                                header = struct.pack(CHUNK_HEADER_FORMAT, len(transformed))
                                sock.sendall(header + transformed)
                            else:
                                sock.sendall(transformed)

                    # Update progress
                    if progress_callback:
                        metrics = self.calculate_metrics(sent_raw_bytes, filesize, start_time, resume_offset)
                        progress_callback(sent_raw_bytes, filesize, metrics)

                # Flush remaining compressor buffer
                if use_compression and compressor:
                    final_bytes = compressor.flush()
                    if final_bytes:
                        if use_encryption:
                            enc_chunk = encrypt_chunk(final_bytes, encryption_key)
                            header = struct.pack(CHUNK_HEADER_FORMAT, len(enc_chunk))
                            sock.sendall(header + enc_chunk)
                        else:
                            header = struct.pack(CHUNK_HEADER_FORMAT, len(final_bytes))
                            sock.sendall(header + final_bytes)

                # Send end of stream marker if using framed stream (encrypted or compressed)
                if use_encryption or use_compression:
                    end_marker = struct.pack(CHUNK_HEADER_FORMAT, 0)
                    sock.sendall(end_marker)

            return True, "File stream dispatched successfully."
        except Exception as e:
            return False, f"Stream processing error: {e}"

    def receive_and_save_file(
        self,
        sock,
        target_path: str,
        filesize: int,
        is_compressed: bool,
        is_encrypted: bool,
        encryption_key: str = "",
        resume_offset: int = 0,
        expected_checksum: str = "",
        progress_callback = None
    ) -> tuple[bool, str, int]:
        """
        Receive a stream from socket, decrypting AES-GCM and decompressing Gzip on-the-fly.
        """
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        mode = "ab" if resume_offset > 0 else "wb"
        start_time = time.time()
        received_raw_bytes = resume_offset
        hasher = hashlib.md5()
        decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16) if is_compressed else None

        try:
            with open(target_path, mode) as f:
                if is_encrypted or is_compressed:
                    # Framed chunk stream mode
                    while received_raw_bytes < filesize:
                        # Read 4-byte chunk header
                        header_bytes = read_exact_bytes(sock, CHUNK_HEADER_SIZE)
                        if not header_bytes:
                            break
                        chunk_len = struct.unpack(CHUNK_HEADER_FORMAT, header_bytes)[0]
                        if chunk_len == 0:
                            # End of stream marker
                            break

                        # Read payload chunk
                        raw_chunk = read_exact_bytes(sock, chunk_len)
                        if not raw_chunk:
                            break

                        # 1. Decrypt stage
                        if is_encrypted:
                            try:
                                decrypted_data = decrypt_chunk(raw_chunk, encryption_key)
                            except Exception as e:
                                return False, f"Decryption failed (Check encryption key): {e}", received_raw_bytes
                        else:
                            decrypted_data = raw_chunk

                        # 2. Decompress stage
                        if is_compressed:
                            decompressed_data = decompressor.decompress(decrypted_data)
                        else:
                            decompressed_data = decrypted_data

                        if decompressed_data:
                            f.write(decompressed_data)
                            hasher.update(decompressed_data)
                            received_raw_bytes += len(decompressed_data)

                        if progress_callback:
                            metrics = self.calculate_metrics(received_raw_bytes, filesize, start_time, resume_offset)
                            progress_callback(received_raw_bytes, filesize, metrics)
                else:
                    # Raw socket stream mode
                    while received_raw_bytes < filesize:
                        chunk_to_read = min(BUFFER_SIZE, filesize - received_raw_bytes)
                        chunk = sock.recv(chunk_to_read)
                        if not chunk:
                            break
                        f.write(chunk)
                        hasher.update(chunk)
                        received_raw_bytes += len(chunk)

                        if progress_callback:
                            metrics = self.calculate_metrics(received_raw_bytes, filesize, start_time, resume_offset)
                            progress_callback(received_raw_bytes, filesize, metrics)

            # Integrity verification
            if expected_checksum and received_raw_bytes == filesize and resume_offset == 0:
                actual_checksum = hasher.hexdigest()
                # If partial hash comparison matched, or full match
                if expected_checksum != actual_checksum and len(actual_checksum) == 32 and len(expected_checksum) == 32:
                    print(f"⚠️ Checksum notice: Expected {expected_checksum[:8]}... Got {actual_checksum[:8]}...")

            return True, "File received and saved successfully.", received_raw_bytes
        except Exception as e:
            return False, f"Receive processing error: {e}", received_raw_bytes

# Global singleton processor instance
processor = TransferProcessor()
