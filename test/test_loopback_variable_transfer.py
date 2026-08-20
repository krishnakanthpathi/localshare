"""
Loopback Variable-Size File Transfer & Speed Benchmark Test

Features:
1. Fast generation of variable-sized test files (e.g. 1 MB, 10 MB, 50 MB, 100 MB, 500 MB, 1 GB).
2. Streaming transfers over loopback (127.0.0.1) with real-time live speed, ETA, and progress metrics.
3. MD5 checksum and data integrity verification between sender and receiver.
4. Performance profiling: throughput (MB/s), peak speed, average speed, transfer duration.
5. Multi-file batch queue test with aggregate progress tracking.
6. Optional file retention (--keep) so generated large files can be reused for testing remote peer devices.
7. Support for configurable compression and AES-256-GCM encryption.

Usage:
  python3 test/test_loopback_variable_transfer.py
  python3 test/test_loopback_variable_transfer.py --sizes 5MB,20MB,100MB
  python3 test/test_loopback_variable_transfer.py --sizes 250MB --keep
  python3 test/test_loopback_variable_transfer.py --sizes 50MB --encrypt
"""

import os
import sys
import time
import uuid
import shutil
import hashlib
import argparse
import tempfile
import threading

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import state, TCP_PORT
from app.queue.manager import queue_manager
from app.queue.models import TransferStatus
from app.transfer.client import send_single_file, send_batch
from app.transfer.server import TCPServer
from app.security.encryption import generate_key

def parse_size_string(size_str: str) -> int:
    """Parse size strings like '500KB', '10MB', '1.5GB', '100M', '50' into bytes."""
    s = size_str.strip().upper()
    units = {
        "B": 1,
        "KB": 1024,
        "K": 1024,
        "MB": 1024 * 1024,
        "M": 1024 * 1024,
        "GB": 1024 * 1024 * 1024,
        "G": 1024 * 1024 * 1024,
    }
    for unit, multiplier in sorted(units.items(), key=lambda x: -len(x[0])):
        if s.endswith(unit):
            num_str = s[:-len(unit)].strip()
            return int(float(num_str) * multiplier)
    return int(float(s))

def format_bytes(size_bytes: int) -> str:
    """Format bytes into readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def compute_md5(filepath: str) -> str:
    """Compute full MD5 hash of a file for integrity verification."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()

def generate_variable_file(folder: str, filename: str, size_bytes: int, compressible: bool = True) -> tuple[str, float]:
    """
    Fast block-based generation of variable-sized test files.
    Returns (filepath, creation_duration_seconds).
    """
    filepath = os.path.join(folder, filename)
    os.makedirs(folder, exist_ok=True)

    start_time = time.time()
    block_size = 1024 * 1024  # 1 MB memory block

    if compressible:
        pattern = b"LocalShare-HighSpeed-Mesh-Transfer-Stream-Test-Payload-0123456789ABCDEF\n"
        base_block = pattern * (block_size // len(pattern) + 1)
        base_block = base_block[:block_size]
    else:
        base_block = os.urandom(block_size)

    written = 0
    with open(filepath, "wb") as f:
        while written < size_bytes:
            to_write = min(block_size, size_bytes - written)
            f.write(base_block[:to_write])
            written += to_write

    creation_time = round(time.time() - start_time, 3)
    return filepath, creation_time

def run_single_transfer_test(
    file_path: str,
    target_port: int,
    receiver_dir: str,
    test_label: str = "Test"
) -> dict:
    """
    Execute streaming file transfer of a variable-size file to loopback address.
    Measures throughput, latency, progress callbacks, and file integrity.
    """
    filename = os.path.basename(file_path)
    filesize = os.path.getsize(file_path)
    rel_path = filename

    print(f"\n🚀 [{test_label}] Transferring {filename} ({format_bytes(filesize)}) -> 127.0.0.1:{target_port}...")

    # Compute source MD5
    sender_md5 = compute_md5(file_path)

    progress_history = []
    speeds = []
    start_time = time.time()

    def _progress_cb(sent_bytes, total_bytes, metrics):
        pct = metrics.get("percent", 0.0)
        speed = metrics.get("speed_mb", 0.0)
        eta = metrics.get("eta", 0.0)
        speeds.append(speed)

        progress_history.append({
            "sent_bytes": sent_bytes,
            "total_bytes": total_bytes,
            "percent": pct,
            "speed_mb": speed,
            "eta": eta,
            "timestamp": time.time()
        })

        # Render live terminal progress bar
        bar_len = 24
        filled = int(bar_len * (pct / 100.0))
        bar = "█" * filled + "░" * (bar_len - filled)
        sys.stdout.write(f"\r   [{bar}] {pct:5.1f}% | {format_bytes(sent_bytes):<10} | Speed: {speed:6.2f} MB/s | ETA: {eta:4.1f}s")
        sys.stdout.flush()

    ok, msg = send_single_file(
        target_ip="127.0.0.1",
        file_path=file_path,
        rel_path=rel_path,
        target_port=target_port,
        progress_callback=_progress_cb
    )
    total_duration = max(time.time() - start_time, 0.001)
    sys.stdout.write("\n")

    avg_speed_mb = (filesize / (1024 * 1024)) / total_duration
    peak_speed_mb = max(speeds) if speeds else avg_speed_mb

    # Verify received file
    received_file_path = os.path.join(receiver_dir, filename)
    file_exists = os.path.exists(received_file_path)
    received_size = os.path.getsize(received_file_path) if file_exists else 0
    receiver_md5 = compute_md5(received_file_path) if file_exists else ""
    integrity_ok = (sender_md5 == receiver_md5) and (received_size == filesize)

    print(f"   Status          : {'✅ SUCCESS' if ok and integrity_ok else '❌ FAILED'} ({msg})")
    print(f"   Duration        : {total_duration:.2f} seconds")
    print(f"   Average Speed   : {avg_speed_mb:.2f} MB/s ({avg_speed_mb * 8:.2f} Mbps)")
    print(f"   Peak Speed      : {peak_speed_mb:.2f} MB/s")
    print(f"   Progress Updates: {len(progress_history)} intermediate callbacks captured")
    print(f"   Integrity Check : {'✅ MD5 MATCH (' + sender_md5[:12] + '...)' if integrity_ok else '❌ MD5 MISMATCH'}")

    return {
        "filename": filename,
        "filesize": filesize,
        "filesize_str": format_bytes(filesize),
        "duration": round(total_duration, 2),
        "avg_speed_mb": round(avg_speed_mb, 2),
        "peak_speed_mb": round(peak_speed_mb, 2),
        "updates_count": len(progress_history),
        "success": ok and integrity_ok,
        "md5_match": integrity_ok,
        "error": msg if not ok else None
    }

def run_batch_transfer_test(
    file_paths: list[str],
    target_port: int,
    receiver_dir: str
) -> dict:
    """Execute multi-file batch transmission and benchmark aggregate progress metrics."""
    total_bytes = sum(os.path.getsize(p) for p in file_paths)
    print(f"\n📦 [Batch Test] Enqueuing {len(file_paths)} files ({format_bytes(total_bytes)} total) -> 127.0.0.1:{target_port}...")

    batch = queue_manager.enqueue_paths(
        target_ip="127.0.0.1",
        paths=file_paths,
        target_name="Loopback-Receiver"
    )

    batch_samples = []
    start_time = time.time()

    def _batch_cb(b, task, metrics):
        pct = b.progress_percent
        speed = metrics.get("speed_mb", 0.0)
        eta = b.eta
        batch_samples.append({
            "pct": pct,
            "transferred": b.transferred_bytes,
            "speed": speed
        })

        bar_len = 24
        filled = int(bar_len * (pct / 100.0))
        bar = "█" * filled + "░" * (bar_len - filled)
        cur_f = f"[{task.filename[:12]} {task.progress_percent:.0f}%]"
        sys.stdout.write(f"\r   [{bar}] {pct:5.1f}% | {cur_f:<18} | Speed: {speed:6.2f} MB/s | ETA: {eta:4.1f}s")
        sys.stdout.flush()

    success_cnt, total_cnt = send_batch(
        target_ip="127.0.0.1",
        batch=batch,
        target_port=target_port,
        batch_progress_callback=_batch_cb
    )
    total_duration = max(time.time() - start_time, 0.001)
    sys.stdout.write("\n")

    avg_speed_mb = (total_bytes / (1024 * 1024)) / total_duration
    all_ok = (success_cnt == total_cnt) and (batch.status == TransferStatus.COMPLETED)

    print(f"   Batch Status    : {'✅ ALL COMPLETED' if all_ok else '❌ INCOMPLETE'} ({success_cnt}/{total_cnt} files)")
    print(f"   Total Duration  : {total_duration:.2f} seconds")
    print(f"   Batch Throughput: {avg_speed_mb:.2f} MB/s")
    print(f"   Aggregate Updates: {len(batch_samples)} samples captured")

    return {
        "total_files": total_cnt,
        "completed_files": success_cnt,
        "total_bytes": total_bytes,
        "duration": round(total_duration, 2),
        "avg_speed_mb": round(avg_speed_mb, 2),
        "success": all_ok
    }

def main():
    parser = argparse.ArgumentParser(description="LocalShare Variable-Size Speed & Progress Benchmark")
    parser.add_argument(
        "--sizes",
        default="1MB,10MB,50MB,100MB",
        help="Comma-separated list of file sizes (e.g. 500KB,10MB,50MB,100MB,500MB,1GB)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=55401,
        help="Loopback TCP port for test receiver (default: 55401)"
    )
    parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Enable AES-256-GCM encryption for the benchmark"
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="Disable Gzip compression (measure raw socket throughput)"
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep generated large files on disk for manual testing with other devices"
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Custom directory to store kept test files (defaults to ~/Downloads/LocalShare_Benchmark_Files)"
    )
    parser.add_argument(
        "--batch-test",
        action="store_true",
        help="Run multi-file batch transfer benchmark in addition to individual size tests"
    )
    args = parser.parse_args()

    # Parse file sizes
    size_tokens = [s.strip() for s in args.sizes.split(",") if s.strip()]
    test_sizes = []
    for token in size_tokens:
        try:
            b = parse_size_string(token)
            test_sizes.append((token, b))
        except Exception as e:
            print(f"⚠️ Could not parse size '{token}': {e}")

    if not test_sizes:
        print("❌ No valid file sizes specified.")
        sys.exit(1)

    # Setup directories
    if args.keep:
        output_dir = args.output_dir or os.path.expanduser("~/Downloads/LocalShare_Benchmark_Files")
        sender_dir = os.path.join(output_dir, "sender")
        receiver_dir = os.path.join(output_dir, "receiver")
        temp_root = None
    else:
        temp_root = tempfile.mkdtemp(prefix="ls_benchmark_")
        sender_dir = os.path.join(temp_root, "sender")
        receiver_dir = os.path.join(temp_root, "receiver")

    os.makedirs(sender_dir, exist_ok=True)
    os.makedirs(receiver_dir, exist_ok=True)

    # Configure application state
    state.upload_dir = receiver_dir
    state.auto_approve = True
    state.compression_enabled = not args.no_compress
    state.encryption_enabled = args.encrypt
    if args.encrypt and not state.encryption_key:
        state.encryption_key = generate_key()

    print("=" * 70)
    print("🚀 LOCALSHARE 2.0 - VARIABLE-SIZE SPEED & PROGRESS BENCHMARK")
    print("=" * 70)
    print(f" 📍 Target Address   : 127.0.0.1:{args.port} (Loopback)")
    print(f" 📦 Test Sizes       : {', '.join(t[0] for t in test_sizes)} ({len(test_sizes)} files)")
    print(f" ⚡ Compression      : {'🟢 Enabled (Gzip)' if state.compression_enabled else '⚪ Disabled (Raw Stream)'}")
    print(f" 🔐 AES-256-GCM      : {'🟢 Enabled' if state.encryption_enabled else '⚪ Disabled'}")
    print(f" 📁 Sender Folder    : {sender_dir}")
    print(f" 📁 Receiver Folder  : {receiver_dir}")
    print(f" 💾 Keep Files       : {'✅ YES (Saved for external peer testing)' if args.keep else '❌ NO (Auto-cleanup)'}")
    print("=" * 70)

    # Start loopback TCP receiver server
    server = TCPServer(port=args.port)
    server.start()
    actual_port = server.port
    print(f"🟢 Loopback TCP Receiver active on port {actual_port}\n")
    time.sleep(0.3)

    results = []
    generated_files = []

    try:
        # Phase 1: Generate test files
        print("🔨 Generating test files...")
        for label, byte_count in test_sizes:
            fname = f"benchmark_file_{label.lower().replace(' ', '')}.dat"
            fpath, gen_time = generate_variable_file(sender_dir, fname, byte_count, compressible=state.compression_enabled)
            generated_files.append((label, fpath, byte_count))
            print(f"   • Created {fname:<30} ({format_bytes(byte_count):<10}) in {gen_time:.2f}s")

        # Phase 2: Run Individual Variable-Size Transfer Tests
        print("\n" + "-" * 70)
        print("📊 EXECUTING STREAMING TRANSFERS & SPEED BENCHMARKS")
        print("-" * 70)

        for label, fpath, byte_count in generated_files:
            res = run_single_transfer_test(
                file_path=fpath,
                target_port=actual_port,
                receiver_dir=receiver_dir,
                test_label=f"Size: {label}"
            )
            results.append(res)

        # Phase 3: Batch Queue Benchmark (if enabled or multiple files)
        batch_res = None
        if args.batch_test or len(generated_files) > 1:
            print("\n" + "-" * 70)
            print("📦 EXECUTING MULTI-FILE BATCH QUEUE BENCHMARK")
            print("-" * 70)
            batch_paths = [f[1] for f in generated_files]
            batch_res = run_batch_transfer_test(batch_paths, actual_port, receiver_dir)

        # Phase 4: Summary Report
        print("\n" + "=" * 70)
        print("🏆 BENCHMARK RESULTS & THROUGHPUT SUMMARY")
        print("=" * 70)
        print(f" {'File Size':<14} | {'Duration':<10} | {'Avg Speed':<14} | {'Peak Speed':<14} | {'Integrity'}")
        print("-" * 70)

        for r in results:
            status_icon = "✅ PASS" if r["success"] else "❌ FAIL"
            print(f" {r['filesize_str']:<14} | {r['duration']:>6.2f}s    | {r['avg_speed_mb']:>7.2f} MB/s   | {r['peak_speed_mb']:>7.2f} MB/s   | {status_icon}")

        if batch_res:
            print("-" * 70)
            print(f" Batch ({batch_res['total_files']} files) : {format_bytes(batch_res['total_bytes'])} in {batch_res['duration']:.2f}s | Throughput: {batch_res['avg_speed_mb']:.2f} MB/s | {'✅ PASS' if batch_res['success'] else '❌ FAIL'}")

        print("=" * 70)

        if args.keep:
            print(f"\n💾 Test files preserved at:")
            print(f"   Sender   : {sender_dir}")
            print(f"   Receiver : {receiver_dir}")
            print(f"👉 You can now use these files to test sending to other Tailscale/LAN devices!")
        else:
            print("\n🧹 Temporary benchmark files cleaned up.")

    finally:
        server.stop()
        if temp_root and os.path.exists(temp_root):
            shutil.rmtree(temp_root, ignore_errors=True)

if __name__ == "__main__":
    main()
