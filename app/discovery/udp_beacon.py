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
        """Return unified list of active LAN and Tailscale peers that have explicitly acknowledged presence."""
        now = time.time()
        active_map = {}

        # Fetch Tailscale peers metadata map for enrichment (IP -> peer dict)
        ts_map = {}
        try:
            for p in get_tailscale_peers():
                ts_map[p["ip"]] = p
                for aip in p.get("all_ips", []):
                    ts_map[aip] = p
        except Exception:
            pass

        # Only include peers that actively sent a packet within TTL
        with self.lock:
            for ip, peer in list(self.peers.items()):
                if now - peer.get("last_seen", 0) <= ttl:
                    custom = get_peer_alias(ip)
                    peer_copy = dict(peer)
                    if custom:
                        peer_copy["name"] = custom
                        peer_copy["custom_alias"] = custom

                    # Enrich with Tailscale metadata if applicable
                    if ip in ts_map or ip.startswith("100."):
                        peer_copy["type"] = "tailscale"
                        ts_info = ts_map.get(ip, {})
                        if ts_info:
                            peer_copy["os"] = ts_info.get("os", peer_copy.get("os", "unknown"))
                            if not custom and ts_info.get("name"):
                                peer_copy["name"] = ts_info["name"]
                    else:
                        peer_copy.setdefault("type", "lan")

                    active_map[ip] = peer_copy

        return list(active_map.values())

    def _listen_loop(self):
        """Listen for UDP broadcast and unicast packets."""
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
                    prev_peer = self.peers.get(sender_ip, {})
                    
                    # For RESPONSE packets, msg["timestamp"] is the echo of our own local timestamp,
                    # so (now - msg["timestamp"]) is the true RTT measured on this machine's clock.
                    # For ANNOUNCE packets, msg["timestamp"] is from the remote clock, so we avoid clock skew.
                    if msg_type == "RESPONSE" and msg.get("ack") and isinstance(msg.get("timestamp"), (int, float)):
                        latency = max(round((now - msg["timestamp"]) * 1000, 1), 0.1)
                    else:
                        latency = prev_peer.get("latency", 0.5)

                    peer_info = {
                        "ip": sender_ip,
                        "name": custom_name or msg.get("name", sender_ip),
                        "port": msg.get("port", TCP_PORT),
                        "web_port": msg.get("web_port", WEB_PORT),
                        "last_seen": now,
                        "latency": latency,
                        "type": "tailscale" if sender_ip.startswith("100.") else "lan",
                        "acknowledged": True
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
                        "timestamp": msg.get("timestamp"),
                        "ack": True
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
        """Send broadcast and unicast announcement packets to discover peers."""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # 1. LAN broadcast targets
        targets = ["255.255.255.255"]
        for ip in self.net_info["all"]:
            parts = ip.split(".")
            if len(parts) == 4 and not ip.startswith("127."):
                subnet_bc = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                if subnet_bc not in targets:
                    targets.append(subnet_bc)

        # 2. Tailscale unicast targets
        try:
            ts_peers = get_tailscale_peers()
            for p in ts_peers:
                tip = p.get("ip")
                if tip and tip not in self.net_info["all"] and tip != "127.0.0.1":
                    if tip not in targets:
                        targets.append(tip)
        except Exception:
            pass

        packet = json.dumps({
            "type": "ANNOUNCE",
            "name": state.device_name,
            "ip": self.primary_ip,
            "tailscale_ip": self.net_info.get("tailscale"),
            "port": TCP_PORT,
            "web_port": WEB_PORT,
            "timestamp": time.time()
        }).encode("utf-8")

        for target in targets:
            try:
                udp_socket.sendto(packet, (target, UDP_PORT))
            except Exception:
                pass
        
        udp_socket.close()

def discover_peers(timeout=2.0) -> list[dict]:
    """
    Active peer scan function for CLI calls and REST API.
    Sends DISCOVER packet to LAN broadcasts and unicast to Tailscale IPs.
    Returns ONLY peers that explicitly respond with an acknowledgment.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    # Bind to ephemeral port (0) to prevent port collisions with any running daemon
    try:
        udp_socket.bind(("0.0.0.0", 0))
    except Exception:
        pass
    udp_socket.settimeout(timeout)

    net_info = get_network_interfaces()
    my_ips = set(net_info["all"])

    # 1. LAN broadcast targets
    targets = ["255.255.255.255"]
    for ip in net_info["all"]:
        parts = ip.split(".")
        if len(parts) == 4 and not ip.startswith("127."):
            targets.append(f"{parts[0]}.{parts[1]}.{parts[2]}.255")

    # 2. Tailscale unicast targets
    ts_map = {}
    try:
        ts_peers = get_tailscale_peers()
        for p in ts_peers:
            tip = p.get("ip")
            if tip:
                ts_map[tip] = p
                for aip in p.get("all_ips", []):
                    ts_map[aip] = p
                if tip not in my_ips and tip != "127.0.0.1":
                    targets.append(tip)
    except Exception:
        pass

    start_time = time.time()
    packet = json.dumps({
        "type": "DISCOVER",
        "name": state.device_name,
        "ip": net_info["primary"],
        "tailscale_ip": net_info.get("tailscale"),
        "port": TCP_PORT,
        "web_port": WEB_PORT,
        "timestamp": start_time
    }).encode("utf-8")

    for target in targets:
        try:
            udp_socket.sendto(packet, (target, UDP_PORT))
        except Exception:
            pass

    peers = {}

    while time.time() - start_time < timeout:
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            break
        udp_socket.settimeout(remaining)
        try:
            data, addr = udp_socket.recvfrom(2048)
            msg = json.loads(data.decode("utf-8", errors="ignore"))
            sender_ip = addr[0]

            if sender_ip not in my_ips and sender_ip != "127.0.0.1":
                custom = get_peer_alias(sender_ip)
                is_ts = sender_ip.startswith("100.") or sender_ip in ts_map
                ts_info = ts_map.get(sender_ip, {})
                resolved_name = custom or (ts_info.get("name") if is_ts and ts_info else None) or msg.get("name", sender_ip)

                msg_type = msg.get("type")
                echoed_ts = msg.get("timestamp")
                if msg_type == "RESPONSE" and msg.get("ack") and isinstance(echoed_ts, (int, float)):
                    rtt = max(round((time.time() - echoed_ts) * 1000, 1), 0.1)
                else:
                    rtt = max(round((time.time() - start_time) * 1000, 1), 0.1)
                now_recv = time.time()
                peers[sender_ip] = {
                    "ip": sender_ip,
                    "name": resolved_name,
                    "port": msg.get("port", TCP_PORT),
                    "web_port": msg.get("web_port", WEB_PORT),
                    "latency": rtt,
                    "last_seen": now_recv,
                    "type": "tailscale" if is_ts else "lan",
                    "os": ts_info.get("os", "unknown") if is_ts else "unknown",
                    "acknowledged": True
                }
        except socket.timeout:
            break
        except Exception:
            continue

    udp_socket.close()

    return list(peers.values())
