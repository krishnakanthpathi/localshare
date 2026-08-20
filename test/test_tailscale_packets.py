"""
Test script for sending discovery packets to Tailscale peer IPs and checking for acknowledgments.
"""

import socket
import json
import time
import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import UDP_PORT, TCP_PORT, WEB_PORT, state
from app.utils import get_network_interfaces
from app.discovery.tailscale import get_tailscale_peers, get_tailscale_status

def test_send_udp_discovery_to_tailscale_peers(timeout=3.0):
    """
    Query Tailscale peers, send unicast UDP DISCOVER packets directly to each Tailscale IP,
    and wait for acknowledgement (RESPONSE) packets.
    Uses an ephemeral/dedicated UDP port so it never conflicts with a running LocalShare instance on port 41234.
    """
    net_info = get_network_interfaces()
    my_ips = set(net_info["all"])
    my_primary = net_info["primary"]
    my_ts_ip = net_info.get("tailscale")

    print("=" * 60)
    print("🧪 TAILSCALE PACKET TRANSMISSION & ACKNOWLEDGEMENT TEST")
    print("=" * 60)
    print(f"📍 Local Primary IP   : {my_primary}")
    print(f"📍 Local Tailscale IP : {my_ts_ip or 'None'}")
    print(f"📍 All Local IPs      : {list(my_ips)}")
    
    # 1. Setup UDP socket bound to ephemeral port (0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 0))
    local_port = sock.getsockname()[1]
    print(f"📍 Test Client UDP Port: {local_port} (Ephemeral, avoiding port conflict)")
    print("-" * 60)

    # 2. Get Tailscale Peers
    ts_peers = get_tailscale_peers()
    print(f"🔍 Discovered {len(ts_peers)} online Tailscale peer(s) from Tailscale daemon:")
    for p in ts_peers:
        print(f"   • {p['name']} -> {p['ip']} (OS: {p.get('os')})")
    
    if not ts_peers:
        print("⚠️ No online Tailscale peers found in Tailscale status.")
        sock.close()
        return []

    print("\n📤 Sending unicast UDP DISCOVER packets directly to Tailscale IPs...")
    sent_targets = []
    for peer in ts_peers:
        target_ip = peer["ip"]
        if target_ip in my_ips or target_ip == my_ts_ip:
            continue
        try:
            packet = json.dumps({
                "type": "DISCOVER",
                "name": state.device_name,
                "ip": my_primary,
                "tailscale_ip": my_ts_ip,
                "port": TCP_PORT,
                "web_port": WEB_PORT,
                "timestamp": time.time()
            }).encode("utf-8")
            sock.sendto(packet, (target_ip, UDP_PORT))
            print(f"   ➡️ Packet sent to {peer['name']} ({target_ip}:{UDP_PORT}) [{len(packet)} bytes]")
            sent_targets.append((target_ip, peer['name']))
        except Exception as e:
            print(f"   ❌ Failed to send packet to {target_ip}: {e}")

    # 3. Listen for incoming responses (acknowledgements)
    print(f"\n📥 Listening for acknowledgments (timeout: {timeout}s)...")
    acknowledged_peers = {}
    start_time = time.time()

    while time.time() - start_time < timeout:
        remaining = timeout - (time.time() - start_time)
        if remaining <= 0:
            break
        sock.settimeout(max(0.1, remaining))
        try:
            data, addr = sock.recvfrom(4096)
            sender_ip = addr[0]
            if sender_ip in my_ips or sender_ip == "127.0.0.1":
                continue

            try:
                msg = json.loads(data.decode("utf-8", errors="ignore"))
            except Exception:
                continue

            msg_type = msg.get("type")
            msg_name = msg.get("name", sender_ip)
            sent_ts = msg.get("timestamp")
            latency = round((time.time() - sent_ts) * 1000, 2) if sent_ts else 0.0

            print(f"   🎉 ACK RECEIVED from {msg_name} ({sender_ip}:{addr[1]})")
            print(f"      Type    : {msg_type}")
            print(f"      Payload : {msg}")
            print(f"      Latency : {latency} ms")

            acknowledged_peers[sender_ip] = {
                "ip": sender_ip,
                "name": msg_name,
                "port": msg.get("port", TCP_PORT),
                "web_port": msg.get("web_port", WEB_PORT),
                "latency": latency,
                "type": "tailscale" if sender_ip.startswith("100.") else "lan",
                "raw_response": msg
            }
        except socket.timeout:
            break
        except Exception as e:
            print(f"   ⚠️ Receive error: {e}")
            break

    sock.close()

    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY & ACKNOWLEDGEMENT RESULTS")
    print("=" * 60)
    print(f"Total Tailscale Peers Targeted : {len(sent_targets)}")
    print(f"Total Peers Acknowledged       : {len(acknowledged_peers)}")

    if acknowledged_peers:
        print("\n✅ Verified Active Peers (Acknowledged):")
        for ip, p in acknowledged_peers.items():
            print(f"   • {p['name']} ({ip}) - Latency: {p['latency']}ms")
    else:
        print("\nℹ️ No peer acknowledged the UDP DISCOVER packet.")
        print("   Possible reasons:")
        print("   1. LocalShare application is not currently running on the remote peer machine(s).")
        print("   2. UDP port 41234 is filtered or blocked by firewall on the remote machine(s).")
        print("   3. Remote peer has not yet joined or enabled LocalShare.")
    print("=" * 60)

    return list(acknowledged_peers.values())

def test_tcp_probe_to_tailscale_peers(timeout=1.5):
    """
    Test direct TCP handshake probe to Tailscale peer TCP ports (4001).
    """
    ts_peers = get_tailscale_peers()
    net_info = get_network_interfaces()
    my_ips = set(net_info["all"])
    my_ts = net_info.get("tailscale")

    print("\n" + "=" * 60)
    print("🧪 TAILSCALE TCP PORT PROBE TEST (TCP 4001)")
    print("=" * 60)

    for p in ts_peers:
        ip = p["ip"]
        if ip in my_ips or ip == my_ts:
            continue
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        start = time.time()
        try:
            s.connect((ip, TCP_PORT))
            lat = round((time.time() - start) * 1000, 2)
            print(f"   🟢 {p['name']} ({ip}:{TCP_PORT}) is REACHABLE (TCP open, {lat}ms)")
            s.close()
        except socket.timeout:
            print(f"   🔴 {p['name']} ({ip}:{TCP_PORT}) - Timeout ({timeout}s)")
        except ConnectionRefusedError:
            print(f"   🟡 {p['name']} ({ip}:{TCP_PORT}) - Connection Refused (Port not open / LocalShare not running)")
        except Exception as e:
            print(f"   🔴 {p['name']} ({ip}:{TCP_PORT}) - Error: {e}")

    print("=" * 60)

if __name__ == "__main__":
    test_send_udp_discovery_to_tailscale_peers(timeout=2.5)
    test_tcp_probe_to_tailscale_peers(timeout=1.5)
