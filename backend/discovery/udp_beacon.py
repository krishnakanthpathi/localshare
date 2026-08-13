"""
UDP Discovery Beacon & Listener
Broadcasts availability and auto-discovers peers on Local WiFi / LAN / Tailscale.
"""

import socket
import json
import time
import threading
import sys
try:
    from config import UDP_PORT, TCP_PORT, WEB_PORT
    from utils import get_network_interfaces, get_tailscale_info
except ImportError:
    from ..config import UDP_PORT, TCP_PORT, WEB_PORT
    from ..utils import get_network_interfaces, get_tailscale_info

class UDPDiscoveryServer:
    def __init__(self, device_name=None):
        self.device_name = device_name or socket.gethostname()
        self.running = False
        self.peers = {}  # ip -> peer metadata dict
        self.lock = threading.Lock()
        self.net_info = get_network_interfaces()
        self.primary_ip = self.net_info["primary"]
        
    def start(self):
        """Start UDP discovery listener and background announcement worker."""
        if self.running:
            return
        self.running = True
        
        # Start receiver thread
        self.recv_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.recv_thread.start()
        
        # Start background announcement thread
        self.beacon_thread = threading.Thread(target=self._beacon_loop, daemon=True)
        self.beacon_thread.start()

    def stop(self):
        self.running = False

    def get_active_peers(self, ttl=15):
        """Return list of active peers discovered within ttl seconds."""
        now = time.time()
        with self.lock:
            active = []
            for ip, peer in list(self.peers.items()):
                if now - peer.get("last_seen", 0) <= ttl:
                    active.append(peer)
            return active

    def _listen_loop(self):
        """Listen for UDP broadcast discover & ping packets."""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if sys.platform != "win32":
            try:
                udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception:
                pass

        try:
            udp_socket.bind(("0.0.0.0", UDP_PORT))
        except Exception as e:
            print(f"⚠️ UDP Discovery socket bind warning: {e}")
            return

        while self.running:
            try:
                udp_socket.settimeout(2.0)
                try:
                    data, addr = udp_socket.recvfrom(2048)
                except socket.timeout:
                    continue

                msg = json.loads(data.decode("utf-8", errors="ignore"))
                msg_type = msg.get("type")
                sender_ip = addr[0]

                # Don't register self as a external peer
                if sender_ip in self.net_info["all"] or sender_ip == "127.0.0.1":
                    continue

                now = time.time()
                if msg_type in ("DISCOVER", "ANNOUNCE", "RESPONSE"):
                    peer_info = {
                        "ip": sender_ip,
                        "name": msg.get("name", sender_ip),
                        "port": msg.get("port", TCP_PORT),
                        "web_port": msg.get("web_port", WEB_PORT),
                        "last_seen": now,
                        "latency": round((now - msg.get("timestamp", now)) * 1000, 1) if msg.get("timestamp") else 0
                    }
                    
                    with self.lock:
                        self.peers[sender_ip] = peer_info

                # If received a DISCOVER, respond directly
                if msg_type == "DISCOVER":
                    reply = json.dumps({
                        "type": "RESPONSE",
                        "name": self.device_name,
                        "ip": self.primary_ip,
                        "port": TCP_PORT,
                        "web_port": WEB_PORT,
                        "timestamp": msg.get("timestamp")
                    }).encode("utf-8")
                    
                    udp_socket.sendto(reply, addr)

            except Exception:
                continue

        udp_socket.close()

    def _beacon_loop(self):
        """Periodically broadcast presence on LAN subnets & Tailscale peers."""
        while self.running:
            self.broadcast_announce()
            try:
                discovered = discover_peers(timeout=1.0)
                now = time.time()
                with self.lock:
                    for peer in discovered:
                        p_ip = peer["ip"]
                        if p_ip not in self.net_info["all"] and p_ip != "127.0.0.1":
                            peer["last_seen"] = now
                            self.peers[p_ip] = peer
            except Exception:
                pass
            time.sleep(5)

    def broadcast_announce(self):
        """Send broadcast announcement packet to discover peers."""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        packet = json.dumps({
            "type": "ANNOUNCE",
            "name": self.device_name,
            "ip": self.primary_ip,
            "port": TCP_PORT,
            "web_port": WEB_PORT,
            "timestamp": time.time()
        }).encode("utf-8")

        discover_packet = json.dumps({
            "type": "DISCOVER",
            "name": self.device_name,
            "ip": self.primary_ip,
            "port": TCP_PORT,
            "web_port": WEB_PORT,
            "timestamp": time.time()
        }).encode("utf-8")

        # Broadcast targets
        targets = ["255.255.255.255"]
        
        # Calculate subnet broadcast IPs (e.g. 192.168.1.255, 192.168.31.255)
        for ip in self.net_info["all"]:
            parts = ip.split(".")
            if len(parts) == 4 and not ip.startswith("127."):
                subnet_bc = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                if subnet_bc not in targets:
                    targets.append(subnet_bc)

        # Include Tailscale online peer IPs as direct targets
        _, ts_peers = get_tailscale_info()
        for ts_ip in ts_peers:
            if ts_ip not in targets and ts_ip not in self.net_info["all"]:
                targets.append(ts_ip)

        for target in targets:
            try:
                udp_socket.sendto(packet, (target, UDP_PORT))
                if target.startswith("100."):
                    udp_socket.sendto(discover_packet, (target, UDP_PORT))
            except Exception:
                pass
        
        udp_socket.close()

def discover_peers(timeout=2.0):
    """
    One-shot active peer scan function for CLI or API calls.
    Sends DISCOVER broadcast and returns list of discovered peers.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.settimeout(timeout)

    net_info = get_network_interfaces()
    my_ips = set(net_info["all"])

    packet = json.dumps({
        "type": "DISCOVER",
        "name": socket.gethostname(),
        "ip": net_info["primary"],
        "timestamp": time.time()
    }).encode("utf-8")

    targets = ["255.255.255.255"]
    for ip in net_info["all"]:
        parts = ip.split(".")
        if len(parts) == 4 and not ip.startswith("127."):
            targets.append(f"{parts[0]}.{parts[1]}.{parts[2]}.255")

    # Include Tailscale online peer IPs
    _, ts_peers = get_tailscale_info()
    for ts_ip in ts_peers:
        if ts_ip not in targets and ts_ip not in my_ips:
            targets.append(ts_ip)

    for target in targets:
        try:
            udp_socket.sendto(packet, (target, UDP_PORT))
        except Exception:
            pass

    start_time = time.time()
    peers = {}

    while time.time() - start_time < timeout:
        try:
            data, addr = udp_socket.recvfrom(2048)
            msg = json.loads(data.decode("utf-8", errors="ignore"))
            sender_ip = addr[0]

            if sender_ip not in my_ips and sender_ip != "127.0.0.1":
                peers[sender_ip] = {
                    "ip": sender_ip,
                    "name": msg.get("name", sender_ip),
                    "port": msg.get("port", TCP_PORT),
                    "web_port": msg.get("web_port", WEB_PORT),
                    "latency": round((time.time() - msg.get("timestamp", time.time())) * 1000, 1)
                }
        except socket.timeout:
            break
        except Exception:
            continue

    udp_socket.close()
    return list(peers.values())
