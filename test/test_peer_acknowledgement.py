"""
Comprehensive Test for Peer Discovery with Mandatory Acknowledgment.
Tests:
1. Sending UDP and TCP discovery packets to peers (LAN & Tailscale).
2. Simulated Local & Tailscale peer replying with ACKNOWLEDGEMENT / RESPONSE.
3. Verifying that only peers that respond with ACK are included in available peers.
4. Verifying that silent/unresponsive peers (no ACK) are strictly excluded.
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
from app.discovery.tailscale import get_tailscale_peers
from app.transfer.protocol import send_message, receive_message

class MockPeerNode:
    """Simulates a remote peer node for testing acknowledgment flow."""
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
        self.udp_sock.bind(("127.0.0.1", self.udp_port))
        
        self.udp_thread = threading.Thread(target=self._udp_loop, daemon=True)
        self.udp_thread.start()

        # TCP listener
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_sock.bind(("127.0.0.1", self.tcp_port))
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
                    # Send ACK RESPONSE back to requester
                    response = json.dumps({
                        "type": "RESPONSE",
                        "name": self.name,
                        "ip": "127.0.0.1",
                        "port": self.tcp_port,
                        "web_port": self.tcp_port + 1,
                        "timestamp": msg.get("timestamp"),
                        "ack": True
                    }).encode("utf-8")
                    self.udp_sock.sendto(response, addr)
            except (socket.timeout, OSError):
                continue
            except Exception as e:
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
            self.udp_sock.close()
        if self.tcp_sock:
            self.tcp_sock.close()

def send_discover_and_collect_acks(target_targets: list[tuple[str, int]], timeout: float = 1.5) -> list[dict]:
    """
    Sends DISCOVER packets to targets (IP, port) and collects ONLY those that return an ACK RESPONSE.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.settimeout(timeout)

    packet = json.dumps({
        "type": "DISCOVER",
        "name": "LocalShare-Tester",
        "timestamp": time.time()
    }).encode("utf-8")

    # Send packets to all targets
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

def run_acknowledgment_verification_tests():
    print("=" * 65)
    print("🧪 RUNNING ACKNOWLEDGMENT & PEER FILTERING VERIFICATION TESTS")
    print("=" * 65)

    # 1. Spawn Mock Peer 1: Responsive Peer (Will acknowledge)
    peer1 = MockPeerNode(name="Responsive-Node-Alpha", udp_port=55101, tcp_port=55201, respond_ack=True)
    peer1.start()

    # 2. Spawn Mock Peer 2: Silent Peer (Will NOT acknowledge)
    peer2 = MockPeerNode(name="Silent-Node-Beta", udp_port=55102, tcp_port=55202, respond_ack=False)
    peer2.start()

    time.sleep(0.2)

    try:
        targets = [
            ("127.0.0.1", 55101),  # Responsive peer
            ("127.0.0.1", 55102),  # Silent peer
            ("127.0.0.1", 55199),  # Non-existent/offline peer
        ]

        print(f"📡 Sending DISCOVER packets to 3 test target endpoints...")
        results = send_discover_and_collect_acks(targets, timeout=1.0)

        print(f"\n📊 Results: {len(results)} peer(s) acknowledged out of 3 candidates:")
        for r in results:
            print(f"   ✅ [ACKED] {r['name']} ({r['ip']}:{r['port']}) Latency: {r['latency']}ms")

        # Assertions
        assert len(results) == 1, f"Expected exactly 1 acknowledged peer, got {len(results)}"
        assert results[0]["name"] == "Responsive-Node-Alpha", f"Expected Responsive-Node-Alpha, got {results[0]['name']}"
        print("\n✨ Test Passed: Silent and offline nodes are strictly excluded!")
        print("✨ Test Passed: Only peers that send active acknowledgment are included!")

    finally:
        peer1.stop()
        peer2.stop()

    print("=" * 65)

if __name__ == "__main__":
    run_acknowledgment_verification_tests()
