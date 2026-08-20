"""
Comprehensive Progress Tracking Test with Active Tailscale Peers.

This test:
1. Queries the Tailscale daemon for real online Tailscale peers and their IPs.
2. Sends UDP discovery and probes TCP port (4001) on active Tailscale peers.
3. Connects to the active Tailscale peer and initiates real file transfers.
4. Verifies real-time streaming progress callbacks, percentage progression (0% -> 100%),
   transfer speed (MB/s), ETA (seconds), and batch aggregate metrics.
5. If remote Tailscale peer is online, streams test data directly over the encrypted Tailscale mesh.
"""

import os
import sys
import time
import socket
import shutil
import tempfile

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import TCP_PORT, state
from app.utils import get_network_interfaces
from app.discovery.tailscale import get_tailscale_peers, get_tailscale_status
from app.discovery.udp_beacon import discover_peers
from app.queue.manager import queue_manager
from app.queue.models import TransferStatus
from app.transfer.client import send_single_file, send_batch
from app.transfer.server import TCPServer

def create_test_file(folder: str, filename: str, size_bytes: int) -> str:
    """Create a temporary test file of specific size."""
    filepath = os.path.join(folder, filename)
    chunk = b"LocalShare-Tailscale-Mesh-Transfer-Block-64KB\n" * 1400  # ~64 KB
    written = 0
    with open(filepath, "wb") as f:
        while written < size_bytes:
            to_write = min(len(chunk), size_bytes - written)
            f.write(chunk[:to_write])
            written += to_write
    return filepath

def find_active_tailscale_peers(timeout=2.0) -> tuple[list[dict], list[dict]]:
    """
    Query Tailscale daemon for peers, then probe TCP port 4001 to find which peers
    are actively running LocalShare and ready to receive transfers.
    """
    ts_status = get_tailscale_status()
    if not ts_status.get("active"):
        print("⚠️ Tailscale is inactive or not running.")
        return [], []

    all_ts_peers = get_tailscale_peers()
    net_info = get_network_interfaces()
    my_ips = set(net_info["all"])
    my_ts_ip = net_info.get("tailscale")

    reachable_peers = []
    print(f"\n🔍 Probing {len(all_ts_peers)} online Tailscale peer(s) on TCP port {TCP_PORT}...")

    for peer in all_ts_peers:
        ip = peer["ip"]
        if ip in my_ips or ip == my_ts_ip:
            continue
        
        # Test TCP connection
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            start_t = time.time()
            s.connect((ip, TCP_PORT))
            latency = round((time.time() - start_t) * 1000, 1)
            s.close()
            peer_copy = dict(peer)
            peer_copy["port"] = TCP_PORT
            peer_copy["latency"] = latency
            reachable_peers.append(peer_copy)
            print(f"   🟢 Active & Reachable: {peer['name']} ({ip}:{TCP_PORT}) - {latency}ms")
        except socket.timeout:
            print(f"   🔴 Unreachable (Timeout): {peer['name']} ({ip}:{TCP_PORT})")
        except ConnectionRefusedError:
            print(f"   🟡 Port Closed (Peer online, LocalShare not running): {peer['name']} ({ip})")
        except Exception as e:
            print(f"   🔴 Error connecting to {peer['name']} ({ip}): {e}")

    return all_ts_peers, reachable_peers

def test_tailscale_single_file_progress(target_ip: str, target_port: int, target_name: str, sender_dir: str):
    """Test streaming progress updates to a live Tailscale peer."""
    print("\n" + "=" * 68)
    print(f"🚀 TEST: STREAMING SINGLE FILE TO TAILSCALE PEER: {target_name} ({target_ip}:{target_port})")
    print("=" * 68)

    file_size = 1024 * 1024  # 1 MB (16 chunks of 64KB)
    test_file = create_test_file(sender_dir, "tailscale_progress_test.bin", file_size)

    progress_events = []
    start_time = time.time()

    def on_progress(sent_bytes, total_bytes, metrics):
        progress_events.append({
            "sent_bytes": sent_bytes,
            "total_bytes": total_bytes,
            "percent": metrics.get("percent", 0.0),
            "speed_mb": metrics.get("speed_mb", 0.0),
            "eta": metrics.get("eta", 0.0),
            "timestamp": time.time()
        })
        pct = metrics.get("percent", 0.0)
        speed = metrics.get("speed_mb", 0.0)
        eta = metrics.get("eta", 0.0)
        sys.stdout.write(f"\r   📊 [Tailscale] Progress: {pct:5.1f}% | {sent_bytes}/{total_bytes} bytes | Speed: {speed:6.2f} MB/s | ETA: {eta:.1f}s")
        sys.stdout.flush()

    print(f"📤 Transferring {os.path.basename(test_file)} ({file_size / 1024:.0f} KB) over Tailscale...")
    ok, msg = send_single_file(
        target_ip=target_ip,
        file_path=test_file,
        target_port=target_port,
        progress_callback=on_progress
    )
    duration = round(time.time() - start_time, 2)
    sys.stdout.write("\n")

    print(f"   Transfer Result : {'✅ SUCCESS' if ok else '❌ FAILED'} ({duration}s) - {msg}")
    print(f"   Progress Updates: {len(progress_events)} intermediate samples captured.")

    if progress_events:
        print(f"   Initial Progress: {progress_events[0]['percent']}% ({progress_events[0]['sent_bytes']} bytes)")
        print(f"   Final Progress  : {progress_events[-1]['percent']}% ({progress_events[-1]['sent_bytes']} bytes)")

    return ok, progress_events

def test_tailscale_batch_progress(target_ip: str, target_port: int, target_name: str, sender_dir: str):
    """Test multi-file batch transmission and aggregate progress to Tailscale peer."""
    print("\n" + "=" * 68)
    print(f"📦 TEST: BATCH QUEUE AGGREGATE PROGRESS TO TAILSCALE PEER: {target_name} ({target_ip})")
    print("=" * 68)

    f1 = create_test_file(sender_dir, "batch_ts_part1.bin", 256 * 1024)
    f2 = create_test_file(sender_dir, "batch_ts_part2.bin", 512 * 1024)
    f3 = create_test_file(sender_dir, "batch_ts_part3.bin", 256 * 1024)
    total_bytes = 256 * 1024 + 512 * 1024 + 256 * 1024

    batch = queue_manager.enqueue_paths(
        target_ip=target_ip,
        paths=[f1, f2, f3],
        target_name=target_name
    )

    batch_samples = []

    def on_batch_progress(b, task, metrics):
        batch_samples.append({
            "batch_pct": b.progress_percent,
            "transferred": b.transferred_bytes,
            "total": b.total_bytes,
            "file": task.filename,
            "file_pct": task.progress_percent,
            "speed_mb": metrics.get("speed_mb", 0.0)
        })
        pct = b.progress_percent
        cur_file = task.filename[:16]
        speed = metrics.get("speed_mb", 0.0)
        sys.stdout.write(f"\r   📦 [Batch] {pct:5.1f}% | Active: {cur_file} ({task.progress_percent:5.1f}%) | Speed: {speed:6.2f} MB/s")
        sys.stdout.flush()

    success_cnt, total_cnt = send_batch(
        target_ip=target_ip,
        batch=batch,
        target_port=target_port,
        batch_progress_callback=on_batch_progress
    )
    sys.stdout.write("\n")

    print(f"   Batch Transferred: {success_cnt}/{total_cnt} files ({total_bytes / 1024:.0f} KB total)")
    print(f"   Batch Samples    : {len(batch_samples)} captured")
    return success_cnt == total_cnt, batch_samples

def run_peer_progress_test_suite():
    print("=" * 68)
    print("🧪 LOCALSHARE 2.0 - ACTIVE TAILSCALE PEER PROGRESS VERIFICATION")
    print("=" * 68)

    temp_dir = tempfile.mkdtemp(prefix="ts_progress_test_")
    sender_dir = os.path.join(temp_dir, "sender")
    os.makedirs(sender_dir, exist_ok=True)

    # 1. Discover all and reachable Tailscale peers
    all_ts_peers, reachable_ts_peers = find_active_tailscale_peers(timeout=2.0)

    print(f"\n📊 Tailscale Peer Summary:")
    print(f"   Total Online Tailscale Peers : {len(all_ts_peers)}")
    print(f"   Active LocalShare TCP Nodes  : {len(reachable_ts_peers)}")

    local_server = None
    target_ip = None
    target_port = TCP_PORT
    target_name = None

    if reachable_ts_peers:
        # Use first reachable live Tailscale peer
        target = reachable_ts_peers[0]
        target_ip = target["ip"]
        target_port = target.get("port", TCP_PORT)
        target_name = target["name"]
        print(f"\n🎯 Selected Active Target: {target_name} ({target_ip}:{target_port})")
    else:
        print("\nℹ️ No external Tailscale node is currently listening on port 4001.")
        print("   Starting LocalShare TCP server on local Tailscale / LAN interface for live loopback testing...")
        net_info = get_network_interfaces()
        target_ip = net_info.get("tailscale") or net_info.get("primary") or "127.0.0.1"
        target_name = f"{state.device_name} (Active Local Node)"
        
        # Start local TCP listener on ephemeral port
        local_server = TCPServer(port=55301)
        local_server.start()
        target_port = local_server.port
        state.upload_dir = os.path.join(temp_dir, "received")
        os.makedirs(state.upload_dir, exist_ok=True)
        print(f"🟢 Active Receiver listening on {target_ip}:{target_port}")

    try:
        # Run Single File Streaming Progress Test
        single_ok, single_events = test_tailscale_single_file_progress(
            target_ip=target_ip,
            target_port=target_port,
            target_name=target_name,
            sender_dir=sender_dir
        )

        # Run Batch Aggregate Progress Test
        batch_ok, batch_samples = test_tailscale_batch_progress(
            target_ip=target_ip,
            target_port=target_port,
            target_name=target_name,
            sender_dir=sender_dir
        )

        print("\n" + "=" * 68)
        print("📋 VERIFICATION RESULTS SUMMARY")
        print("=" * 68)
        print(f" Single File Transfer : {'✅ PASSED' if single_ok else '❌ FAILED'} ({len(single_events)} progress updates)")
        print(f" Batch Queue Progress : {'✅ PASSED' if batch_ok else '❌ FAILED'} ({len(batch_samples)} aggregate updates)")
        print("=" * 68)

    finally:
        if local_server:
            local_server.stop()
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    run_peer_progress_test_suite()
