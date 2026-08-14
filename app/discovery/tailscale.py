"""
Tailscale Discovery & Real-Time Node Resolver
Queries Tailscale daemon status, discovers online Tailscale mesh nodes, and maps IPs to friendly names.
"""

import json
import shutil
import subprocess
from app.db.mongo import get_peer_alias

def find_tailscale_binary() -> str | None:
    """Locate tailscale CLI binary across macOS, Linux, and Windows."""
    paths = [
        shutil.which("tailscale"),
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
        "/usr/local/bin/tailscale",
        "/usr/bin/tailscale",
        "C:\\Program Files\\Tailscale\\tailscale.exe"
    ]
    for p in paths:
        if p and shutil.which(p):
            return p
    return None

def get_tailscale_status() -> dict:
    """Query Tailscale daemon for complete JSON network status."""
    ts_bin = find_tailscale_binary()
    if not ts_bin:
        return {"active": False, "reason": "Tailscale binary not found."}

    try:
        res = subprocess.run([ts_bin, "status", "--json"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            data["active"] = True
            return data
        return {"active": False, "reason": f"Status return code {res.returncode}: {res.stderr.strip()}"}
    except Exception as e:
        return {"active": False, "reason": str(e)}

def get_tailscale_peers() -> list[dict]:
    """
    Get list of all active online Tailscale peers with resolved friendly names.
    """
    status = get_tailscale_status()
    if not status.get("active"):
        return []

    self_ips = status.get("Self", {}).get("TailscaleIPs", [])
    self_node_name = status.get("Self", {}).get("HostName", "")

    online_peers = []
    peers_dict = status.get("Peer", {}) or {}

    for node_key, peer in peers_dict.items():
        if not peer.get("Online"):
            continue

        ts_ips = peer.get("TailscaleIPs", [])
        if not ts_ips:
            continue

        primary_ts_ip = ts_ips[0]
        # Ignore self
        if primary_ts_ip in self_ips:
            continue

        host_name = peer.get("HostName", primary_ts_ip)
        dns_name = peer.get("DNSName", "").rstrip(".")
        os_type = peer.get("OS", "unknown")

        # Check for custom user-assigned alias in MongoDB
        custom_alias = get_peer_alias(primary_ts_ip)
        display_name = custom_alias or host_name

        online_peers.append({
            "ip": primary_ts_ip,
            "all_ips": ts_ips,
            "name": display_name,
            "hostname": host_name,
            "dns_name": dns_name,
            "os": os_type,
            "custom_alias": custom_alias,
            "type": "tailscale",
            "online": True
        })

    return online_peers

def resolve_peer_name(ip: str, default_name: str = None) -> str:
    """Resolve an IP into custom alias, Tailscale hostname, or default."""
    custom = get_peer_alias(ip)
    if custom:
        return custom
    
    # Check Tailscale status
    ts_peers = get_tailscale_peers()
    for p in ts_peers:
        if p["ip"] == ip or ip in p.get("all_ips", []):
            return p["name"]

    return default_name or ip
