"""
Official FastMCP Server for LocalShare
Exposes file transfer queueing, Tailscale peer discovery, settings, and encryption controls to AI agents.
"""

from mcp.server.fastmcp import FastMCP
from app.config import state
from app.db.mongo import load_settings, save_settings, get_settings_dict, set_peer_alias, get_all_peer_aliases
from app.discovery.udp_beacon import discover_peers
from app.discovery.tailscale import get_tailscale_peers, get_tailscale_status
from app.queue.manager import queue_manager
from app.transfer.client import send_text_snippet
from app.sync.clipboard import broadcast_text
from app.security.encryption import generate_key

# Load settings from MongoDB
load_settings()

mcp = FastMCP("LocalShare")

@mcp.tool()
def localshare_discover_peers(timeout: float = 2.0) -> dict:
    """Discover active LAN and Tailscale peers with resolved friendly names."""
    peers = discover_peers(timeout=timeout)
    return {"status": "success", "peers": peers}

@mcp.tool()
def localshare_get_tailscale_status() -> dict:
    """Get real-time Tailscale network status and online mesh nodes."""
    status = get_tailscale_status()
    peers = get_tailscale_peers()
    return {"status": "success", "active": status.get("active", False), "peers": peers}

@mcp.tool()
def localshare_queue_folders_and_files(target_ip: str, paths: list[str], target_name: str = "") -> dict:
    """
    Queue multiple folders and files simultaneously for high-speed transfer to a target IP.
    """
    batch = queue_manager.enqueue_paths(target_ip=target_ip, paths=paths, target_name=target_name)
    return {"status": "success", "batch_id": batch.id, "total_files": len(batch.tasks), "total_bytes": batch.total_bytes}

@mcp.tool()
def localshare_get_queue_status() -> dict:
    """Get status of all queued and completed batch transfers."""
    batches = queue_manager.get_all_batches()
    return {"status": "success", "batches": batches}

@mcp.tool()
def localshare_send_text(text: str, target_ip: str = "") -> dict:
    """Share text snippet with a specific peer IP or broadcast to all active peers."""
    if target_ip:
        ok, msg = send_text_snippet(target_ip, text)
        return {"status": "success" if ok else "error", "message": msg}
    else:
        peers = discover_peers(timeout=1.0)
        count = broadcast_text(text, peers)
        return {"status": "success", "broadcast_count": count}

@mcp.tool()
def localshare_set_peer_name(ip: str, custom_name: str, notes: str = "") -> dict:
    """Assign or update a custom friendly name for any LAN or Tailscale IP in MongoDB."""
    ok = set_peer_alias(ip, custom_name, notes)
    return {"status": "success" if ok else "error", "ip": ip, "name": custom_name}

@mcp.tool()
def localshare_get_settings() -> dict:
    """Retrieve full application settings (upload dir, encryption, compression, auto-approve)."""
    return {"status": "success", "settings": get_settings_dict(), "peer_aliases": get_all_peer_aliases()}

@mcp.tool()
def localshare_update_settings(
    auto_approve: bool = None,
    upload_dir: str = None,
    encryption_enabled: bool = None,
    encryption_key: str = None,
    compression_enabled: bool = None
) -> dict:
    """Update settings in MongoDB and runtime engine."""
    updates = {}
    if auto_approve is not None:
        updates["auto_approve"] = auto_approve
    if upload_dir is not None:
        updates["upload_dir"] = upload_dir
    if encryption_enabled is not None:
        updates["encryption_enabled"] = encryption_enabled
    if encryption_key is not None:
        updates["encryption_key"] = encryption_key
    if compression_enabled is not None:
        updates["compression_enabled"] = compression_enabled
    
    saved = save_settings(updates)
    return {"status": "success", "settings": saved}

@mcp.tool()
def localshare_generate_encryption_key() -> dict:
    """Generate a new random AES-256 key."""
    key = generate_key()
    return {"status": "success", "key": key}

def run_mcp_service():
    """Run FastMCP stdio service loop."""
    print("🤖 Starting LocalShare FastMCP Service...")
    mcp.run()

if __name__ == "__main__":
    run_mcp_service()
