"""
Comprehensive Test for Peer Discovery with Mandatory Acknowledgment.

Tests:
1. Active Tailscale Peer Discovery: Queries online Tailscale mesh nodes and tests direct UDP ACK packets.
2. Responsive vs Silent Peer Verification: Tests simulated active peer (sends ACK) vs silent/offline peer (no ACK).
3. Verifying that only peers that respond with explicit ACKNOWLEDGEMENT are marked active.
4. Verifying that silent, dead, or non-acknowledging peers are strictly excluded.
"""

import socket
import json
import time
import threading
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import UDP_PORT, TCP_PORT, WEB_PORT, state
from app.utils import get_network_interfaces
from app.discovery.tailscale import get_tailscale_peers, get_tailscale_status
from app.discovery.udp_beacon import discover_peers
from app.transfer.protocol import send_message, receive_message

class MockPeerNode:
    """Simulates a peer node for deterministic acknowledgment verification."""
    def __init__(self, name: str, udp_port: int, tcp_port: int, respond_ack: bool = True):
        self.name = name
        self.udp_port = udp_port
        self.tcp_port = tcp_port
        self.respond_ack = respond_ack
        self.running = False
        self.udp_sock = None
        self.tcp_sock = None

    def start(self):
        self.running = True
        # UDP listener
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_sock.bind(("0.0.0.0", self.udp_port))
        
        self.udp_thread = threading.Thread(target=self._udp_loop, daemon=True)
        self.udp_thread.start()

        # TCP listener
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_sock.bind(("0.0.0.0", self.tcp_port))
        self.tcp_sock.listen(5)

        self.tcp_thread = threading.Thread(target=self._tcp_loop, daemon=True)
        self.tcp_thread.start()

    def _udp_loop(self):
        while self.running:
            try:
                self.udp_sock.settimeout(0.5)
                data, addr = self.udp_sock.recvfrom(2048)
                msg = json.loads(data.decode("utf-8"))
                
                if msg.get("type") == "DISCOVER" and self.respond_ack:
                    response = json.dumps({
                        "type": "RESPONSE",
                        "name": self.name,
                        "ip": addr[0],
                        "port": self.tcp_port,
                        "web_port": self.tcp_port + 1,
                        "timestamp": msg.get("timestamp"),
                        "ack": True
                    }).encode("utf-8")
                    self.udp_sock.sendto(response, addr)
            except (socket.timeout, OSError):
                continue
            except Exception:
                pass

    def _tcp_loop(self):
        while self.running:
            try:
                self.tcp_sock.settimeout(0.5)
                client, addr = self.tcp_sock.accept()
                msg = receive_message(client)
                if msg and msg.get("type") == "PING" and self.respond_ack:
                    send_message(client, {
                        "type": "PONG",
                        "name": self.name,
                        "port": self.tcp_port,
                        "ack": True
                    })
                client.close()
            except (socket.timeout, OSError):
                continue
            except Exception:
                pass

    def stop(self):
        self.running = False
        if self.udp_sock:
            try:
                self.udp_sock.close()
            except Exception:
                pass
        if self.tcp_sock:
            try:
                self.tcp_sock.close()
            except Exception:
                pass

def send_discover_and_collect_acks(target_targets: list[tuple[str, int]], timeout: float = 1.5) -> list[dict]:
    """Sends DISCOVER packets to targets (IP, port) and collects ONLY those that return an ACK RESPONSE."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        udp_socket.bind(("0.0.0.0", 0))
    except Exception:
        pass
    udp_socket.settimeout(timeout)

    packet = json.dumps({
        "type": "DISCOVER",
        "name": state.device_name,
        "timestamp": time.time()
    }).encode("utf-8")

    for ip, port in target_targets:
        try:
            udp_socket.sendto(packet, (ip, port))
        except Exception as e:
            print(f"Error sending to {ip}:{port} -> {e}")

    acknowledged_peers = {}
    start_time = time.time()

    while time.time() - start_time < timeout:
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            break
        udp_socket.settimeout(remaining)
        try:
            data, addr = udp_socket.recvfrom(2048)
            msg = json.loads(data.decode("utf-8", errors="ignore"))
            if msg.get("type") == "RESPONSE":
                sender_ip = addr[0]
                acknowledged_peers[f"{sender_ip}:{msg.get('port', addr[1])}"] = {
                    "ip": sender_ip,
                    "name": msg.get("name", sender_ip),
                    "port": msg.get("port", TCP_PORT),
                    "web_port": msg.get("web_port", WEB_PORT),
                    "latency": round((time.time() - msg.get("timestamp", time.time())) * 1000, 2),
                    "acknowledged": True
                }
        except socket.timeout:
            break
        except Exception:
            continue

    udp_socket.close()
    return list(acknowledged_peers.values())

def test_live_tailscale_peer_discovery(timeout=2.0):
    """Query live Tailscale peers and test discovery ACK over Tailscale mesh."""
    print("\n" + "=" * 65)
    print("🌐 STAGE 1: LIVE TAILSCALE PEER DISCOVERY & ACKNOWLEDGMENT")
    print("=" * 65)

    ts_peers = get_tailscale_peers()
    net_info = get_network_interfaces()
    my_ips = set(net_info["all"])
    my_ts_ip = net_info.get("tailscale")

    print(f"📍 Local Tailscale IP: {my_ts_ip or 'None'}")
    print(f"📍 Online Tailscale Peers Found: {len(ts_peers)}")

    targets = []
    for p in ts_peers:
        ip = p["ip"]
        if ip not in my_ips and ip != my_ts_ip:
            targets.append((ip, UDP_PORT))
            print(f"   • Peer: {p['name']} -> {ip}:{UDP_PORT} (OS: {p.get('os')})")

    if not targets:
        print("ℹ️ No remote Tailscale peers to probe.")
        return []

    print(f"\n📤 Sending UDP discovery packets to {len(targets)} Tailscale peer(s)...")
    acks = send_discover_and_collect_acks(targets, timeout=timeout)
    print(f"📥 Received {len(acks)} acknowledgment(s) from Tailscale peers.")
    for a in acks:
        print(f"   ✅ ACK from {a['name']} ({a['ip']}) - Latency: {a['latency']}ms")
    return acks

def test_acknowledgment_filtering():
    """Verify strict inclusion of acknowledging nodes and exclusion of silent nodes."""
    print("\n" + "=" * 65)
    print("🧪 STAGE 2: CONTROLLED ACKNOWLEDGMENT & SILENT NODE FILTERING")
    print("=" * 65)

    peer1 = MockPeerNode(name="Responsive-Node-Alpha", udp_port=55101, tcp_port=55201, respond_ack=True)
    peer1.start()

    peer2 = MockPeerNode(name="Silent-Node-Beta", udp_port=55102, tcp_port=55202, respond_ack=False)
    peer2.start()

    time.sleep(0.2)

    try:
        targets = [
            ("127.0.0.1", 55101),  # Responsive peer (Sends ACK)
            ("127.0.0.1", 55102),  # Silent peer (No ACK)
            ("127.0.0.1", 55199),  # Non-existent offline port
        ]

        print(f"📡 Sending DISCOVER packets to 3 test target endpoints...")
        results = send_discover_and_collect_acks(targets, timeout=1.0)

        print(f"\n📊 Results: {len(results)} peer(s) acknowledged out of 3 candidates:")
        for r in results:
            print(f"   ✅ [ACKED] {r['name']} ({r['ip']}:{r['port']}) Latency: {r['latency']}ms")

        # Assertions
        assert len(results) == 1, f"Expected exactly 1 acknowledged peer, got {len(results)}"
        assert results[0]["name"] == "Responsive-Node-Alpha", f"Expected Responsive-Node-Alpha, got {results[0]['name']}"
        print("\n✨ Verified: Silent and offline nodes are strictly excluded!")
        print("✨ Verified: Only peers with active acknowledgments are reported!")
    finally:
        peer1.stop()
        peer2.stop()

def run_all():
    print("=" * 65)
    print("🧪 PEER DISCOVERY & ACKNOWLEDGMENT TEST SUITE")
    print("=" * 65)
    test_live_tailscale_peer_discovery()
    test_acknowledgment_filtering()
    print("\n" + "=" * 65)
    print("🎉 ALL PEER ACKNOWLEDGMENT TESTS COMPLETED!")
    print("=" * 65)

if __name__ == "__main__":
    run_all()
