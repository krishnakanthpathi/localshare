"""
UDP Discovery Beacon & Mesh Listener
Broadcasts availability and auto-discovers peers across LAN and Tailscale subnets.
"""

import socket
import json
import time
import threading
import sys
from app.config import UDP_PORT, TCP_PORT, WEB_PORT, state
from app.utils import get_network_interfaces
from app.db.mongo import get_peer_alias
from app.discovery.tailscale import get_tailscale_peers

class UDPDiscoveryServer:
    """Background listener and beacon announcer for local mesh discovery."""

    def __init__(self, device_name=None):
        self.device_name = device_name or state.device_name
        self.running = False
        self.peers = {}  # ip -> peer dict
        self.lock = threading.Lock()
        self.net_info = get_network_interfaces()
        self.primary_ip = self.net_info["primary"]
        
    def start(self):
        """Start UDP discovery listener and background announcement worker."""
        if self.running:
            return
        self.running = True
        
        self.recv_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.recv_thread.start()
        
        self.beacon_thread = threading.Thread(target=self._beacon_loop, daemon=True)
        self.beacon_thread.start()

    def stop(self):
        self.running = False

    def get_active_peers(self, ttl=15) -> list[dict]:
        """Return unified list of active LAN and Tailscale peers with resolved custom names."""
        now = time.time()
        active_map = {}

        # 1. LAN discovered peers
        with self.lock:
            for ip, peer in list(self.peers.items()):
                if now - peer.get("last_seen", 0) <= ttl:
                    custom = get_peer_alias(ip)
                    peer_copy = dict(peer)
                    if custom:
                        peer_copy["name"] = custom
                        peer_copy["custom_alias"] = custom
                    active_map[ip] = peer_copy

        # 2. Tailscale online peers
        try:
            ts_peers = get_tailscale_peers()
            for p in ts_peers:
                ip = p["ip"]
                if ip not in active_map:
                    active_map[ip] = {
                        "ip": ip,
                        "name": p["name"],
                        "port": TCP_PORT,
                        "web_port": WEB_PORT,
                        "type": "tailscale",
                        "os": p.get("os", "unknown"),
                        "last_seen": now,
                        "latency": 0.0
                    }
        except Exception:
            pass

        return list(active_map.values())

    def _listen_loop(self):
        """Listen for UDP broadcast packets."""
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

                if sender_ip in self.net_info["all"] or sender_ip == "127.0.0.1":
                    continue

                now = time.time()
                if msg_type in ("DISCOVER", "ANNOUNCE", "RESPONSE"):
                    custom_name = get_peer_alias(sender_ip)
                    peer_info = {
                        "ip": sender_ip,
                        "name": custom_name or msg.get("name", sender_ip),
                        "port": msg.get("port", TCP_PORT),
                        "web_port": msg.get("web_port", WEB_PORT),
                        "last_seen": now,
                        "latency": round((now - msg.get("timestamp", now)) * 1000, 1) if msg.get("timestamp") else 0
                    }
                    
                    with self.lock:
                        self.peers[sender_ip] = peer_info

                if msg_type == "DISCOVER":
                    reply = json.dumps({
                        "type": "RESPONSE",
                        "name": state.device_name,
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
            time.sleep(5)

    def broadcast_announce(self):
        """Send broadcast announcement packet to discover peers."""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        packet = json.dumps({
            "type": "ANNOUNCE",
            "name": state.device_name,
            "ip": self.primary_ip,
            "port": TCP_PORT,
            "web_port": WEB_PORT,
            "timestamp": time.time()
        }).encode("utf-8")

        targets = ["255.255.255.255"]
        for ip in self.net_info["all"]:
            parts = ip.split(".")
            if len(parts) == 4 and not ip.startswith("127."):
                subnet_bc = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                if subnet_bc not in targets:
                    targets.append(subnet_bc)

        for target in targets:
            try:
                udp_socket.sendto(packet, (target, UDP_PORT))
            except Exception:
                pass
        
        udp_socket.close()

def discover_peers(timeout=2.0) -> list[dict]:
    """
    Active peer scan function for CLI calls.
    Sends DISCOVER broadcast and returns list of discovered LAN & Tailscale peers.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.settimeout(timeout)

    net_info = get_network_interfaces()
    my_ips = set(net_info["all"])

    packet = json.dumps({
        "type": "DISCOVER",
        "name": state.device_name,
        "ip": net_info["primary"],
        "timestamp": time.time()
    }).encode("utf-8")

    targets = ["255.255.255.255"]
    for ip in net_info["all"]:
        parts = ip.split(".")
        if len(parts) == 4 and not ip.startswith("127."):
            targets.append(f"{parts[0]}.{parts[1]}.{parts[2]}.255")

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
                custom = get_peer_alias(sender_ip)
                peers[sender_ip] = {
                    "ip": sender_ip,
                    "name": custom or msg.get("name", sender_ip),
                    "port": msg.get("port", TCP_PORT),
                    "web_port": msg.get("web_port", WEB_PORT),
                    "latency": round((time.time() - msg.get("timestamp", time.time())) * 1000, 1),
                    "type": "lan"
                }
        except socket.timeout:
            break
        except Exception:
            continue

    udp_socket.close()

    # Merge Tailscale peers
    try:
        ts_peers = get_tailscale_peers()
        for p in ts_peers:
            ip = p["ip"]
            if ip not in peers:
                peers[ip] = {
                    "ip": ip,
                    "name": p["name"],
                    "port": TCP_PORT,
                    "web_port": WEB_PORT,
                    "latency": 0.0,
                    "type": "tailscale",
                    "os": p.get("os", "unknown")
                }
    except Exception:
        pass

    return list(peers.values())
