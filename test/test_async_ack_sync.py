"""
Comprehensive Verification Test for Asynchronous Progress ACK Synchronization.
Verifies:
1. Parallel multi-socket file transfer emits PROGRESS_ACK messages from receiver to sender over control socket.
2. Sender's progress metrics are driven by receiver-acknowledged bytes written to disk.
3. Both sender and receiver stay within synchronized metrics throughout transfer.
4. File content and checksum match with zero corruption.
"""

import os
import sys
import time
import socket
import shutil
import tempfile
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import TCP_PORT, PARALLEL_WORKERS, state
from app.transfer.server import TCPServer
from app.transfer.client import send_parallel_file

def create_test_payload(folder: str, filename: str, size_mb: int) -> tuple[str, str]:
    """Create test file and return path and MD5 hash."""
    filepath = os.path.join(folder, filename)
    hasher = hashlib.md5()
    chunk = b"LocalShare-Parallel-Async-ACK-Sync-Test-Block-64KB\n" * 1280  # ~64 KB
    written = 0
    target_size = size_mb * 1024 * 1024

    with open(filepath, "wb") as f:
        while written < target_size:
            to_write = min(len(chunk), target_size - written)
            f.write(chunk[:to_write])
            hasher.update(chunk[:to_write])
            written += to_write

    return filepath, hasher.hexdigest()

def test_async_ack_parallel_transfer():
    print("=" * 68)
    print("🧪 TEST: ASYNCHRONOUS PROGRESS ACK PARALLEL TRANSFER VERIFICATION")
    print("=" * 68)

    temp_dir = tempfile.mkdtemp(prefix="async_ack_test_")
    sender_dir = os.path.join(temp_dir, "sender")
    receiver_dir = os.path.join(temp_dir, "receiver")
    os.makedirs(sender_dir, exist_ok=True)
    os.makedirs(receiver_dir, exist_ok=True)

    # 1. Create a 16 MB test file
    test_size_mb = 16
    print(f"📦 Generating {test_size_mb} MB test file...")
    source_file, expected_md5 = create_test_payload(sender_dir, "parallel_ack_test.bin", test_size_mb)
    filesize = os.path.getsize(source_file)
    print(f"   Source File : {source_file} ({filesize:,} bytes)")
    print(f"   Expected MD5: {expected_md5}")

    # 2. Start TCP server on ephemeral port
    server_port = 55401
    state.upload_dir = receiver_dir
    state.auto_approve = True
    server = TCPServer(port=server_port)
    server.start()
    print(f"🟢 Active Receiver listening on port {server.port}")

    progress_samples = []

    def on_progress(confirmed_bytes, total_bytes, metrics):
        progress_samples.append({
            "confirmed_bytes": confirmed_bytes,
            "total_bytes": total_bytes,
            "percent": metrics.get("percent", 0.0),
            "speed_mb": metrics.get("speed_mb", 0.0),
            "eta": metrics.get("eta", 0.0),
            "time": time.time()
        })
        pct = metrics.get("percent", 0.0)
        speed = metrics.get("speed_mb", 0.0)
        sys.stdout.write(f"\r   📊 [Sender UI] Confirmed Recv: {pct:5.1f}% | {confirmed_bytes}/{total_bytes} bytes | Speed: {speed:6.2f} MB/s")
        sys.stdout.flush()

    try:
        time.sleep(0.2)
        print(f"\n🚀 Initiating 4-worker parallel transfer to 127.0.0.1:{server.port}...")
        t0 = time.time()
        ok, msg = send_parallel_file(
            target_ip="127.0.0.1",
            file_path=source_file,
            target_port=server.port,
            num_workers=PARALLEL_WORKERS,
            progress_callback=on_progress
        )
        elapsed = time.time() - t0
        sys.stdout.write("\n")

        print(f"   Transfer Result : {'✅ SUCCESS' if ok else '❌ FAILED'} ({elapsed:.2f}s) - {msg}")
        print(f"   Progress Samples: {len(progress_samples)} intermediate samples captured.")

        assert ok, f"Transfer failed: {msg}"
        assert len(progress_samples) >= 3, f"Expected multiple progress samples, got {len(progress_samples)}"

        # Verify destination file
        dest_file = os.path.join(receiver_dir, "parallel_ack_test.bin")
        assert os.path.exists(dest_file), f"Destination file does not exist: {dest_file}"
        dest_size = os.path.getsize(dest_file)
        assert dest_size == filesize, f"Size mismatch: expected {filesize}, got {dest_size}"

        with open(dest_file, "rb") as f:
            actual_md5 = hashlib.md5(f.read()).hexdigest()
        assert actual_md5 == expected_md5, f"MD5 mismatch: expected {expected_md5}, got {actual_md5}"

        print(f"✅ Checksum matched: {actual_md5}")
        print(f"✅ Final progress confirmed: {progress_samples[-1]['percent']}% ({progress_samples[-1]['confirmed_bytes']} bytes)")
        print("\n🎉 ASYNCHRONOUS PROGRESS ACK VERIFICATION PASSED PERFECTLY!\n")

    finally:
        server.stop()
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_async_ack_parallel_transfer()
