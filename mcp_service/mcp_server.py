"""
Official FastMCP Server for LocalShare
Provides high-performance Model Context Protocol integration for AI agents (Antigravity, Claude, Cursor).
"""

from mcp.server.fastmcp import FastMCP
import socket
from ..config import state
from ..discovery.udp_beacon import discover_peers
from ..transfer.client import TCPClientEngine
from ..sync.clipboard import ClipboardManager

mcp = FastMCP("LocalShare")

@mcp.tool()
def localshare_discover_peers(timeout: float = 2.0) -> dict:
    """
    Discover active LocalShare peer devices on the local network (LAN / Tailscale).
    """
    peers = discover_peers(timeout=timeout)
    return {"status": "success", "peers": peers}

@mcp.tool()
def localshare_send_file(target_ip: str, file_path: str) -> dict:
    """
    Send a local file or folder to a target peer device IP on the network.
    """
    ok, msg = TCPClientEngine.send_path(target_ip, file_path)
    return {"status": "success" if ok else "error", "message": msg}

@mcp.tool()
def localshare_send_text(text: str, target_ip: str = "") -> dict:
    """
    Share a text snippet or clipboard content with a peer device or broadcast to all peers.
    """
    if target_ip:
        ok, msg = TCPClientEngine.send_text_snippet(target_ip, text)
        return {"status": "success" if ok else "error", "message": msg}
    else:
        peers = discover_peers(timeout=1.5)
        count = ClipboardManager.broadcast_text(text, peers)
        return {"status": "success", "broadcast_count": count}

@mcp.tool()
def localshare_get_transfers() -> dict:
    """
    Get status of active and recent file transfers.
    """
    return {"status": "success", "transfers": state.transfers}

@mcp.tool()
def localshare_toggle_approval(auto_approve: bool) -> dict:
    """
    Toggle auto-approval setting for incoming file transfers.
    """
    state.auto_approve = auto_approve
    return {"status": "success", "auto_approve": state.auto_approve}

def run_mcp_server():
    """Run FastMCP stdio server loop."""
    mcp.run()
