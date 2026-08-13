"""
Official FastMCP Server for LocalShare
Provides high-performance Model Context Protocol integration for AI agents (Antigravity, Claude, Cursor).
"""

import os
import sys
import json
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP

# Ensure parent and backend directories are in sys.path
mcp_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.abspath(os.path.join(mcp_dir, ".."))
backend_dir = os.path.abspath(os.path.join(parent_dir, "backend"))

for d in [backend_dir, parent_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)
if mcp_dir not in sys.path:
    sys.path.append(mcp_dir)

from mcp_config import BACKEND_API_URL, MCP_PORT

# Try direct python backend imports
try:
    from config import state
    from discovery.udp_beacon import discover_peers
    from transfer.client import TCPClientEngine
    from sync.clipboard import ClipboardManager
    HAS_DIRECT_BACKEND = True
except ImportError:
    try:
        from localshare.backend.config import state
        from localshare.backend.discovery.udp_beacon import discover_peers
        from localshare.backend.transfer.client import TCPClientEngine
        from localshare.backend.sync.clipboard import ClipboardManager
        HAS_DIRECT_BACKEND = True
    except ImportError:
        HAS_DIRECT_BACKEND = False

mcp = FastMCP("LocalShare")

@mcp.tool()
def localshare_discover_peers(timeout: float = 2.0) -> dict:
    """
    Discover active LocalShare peer devices on the local network (LAN / Tailscale).
    """
    if HAS_DIRECT_BACKEND:
        peers = discover_peers(timeout=timeout)
        return {"status": "success", "peers": peers}
    else:
        try:
            req = urllib.request.Request(f"{BACKEND_API_URL}/api/peers")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                peers = json.loads(response.read().decode())
                return {"status": "success", "peers": peers}
        except Exception as e:
            return {"status": "error", "message": f"Backend API call failed: {e}", "peers": []}

@mcp.tool()
def localshare_send_file(target_ip: str, file_path: str) -> dict:
    """
    Send a local file or folder to a target peer device IP on the network.
    """
    if HAS_DIRECT_BACKEND:
        ok, msg = TCPClientEngine.send_path(target_ip, file_path)
        return {"status": "success" if ok else "error", "message": msg}
    else:
        return {"status": "error", "message": "Direct TCP client engine required for raw file transfer."}

@mcp.tool()
def localshare_send_text(text: str, target_ip: str = "") -> dict:
    """
    Share a text snippet or clipboard content with a peer device or broadcast to all peers.
    """
    if HAS_DIRECT_BACKEND:
        if target_ip:
            ok, msg = TCPClientEngine.send_text_snippet(target_ip, text)
            return {"status": "success" if ok else "error", "message": msg}
        else:
            peers = discover_peers(timeout=1.5)
            count = ClipboardManager.broadcast_text(text, peers)
            return {"status": "success", "broadcast_count": count}
    else:
        try:
            data = json.dumps({"text": text, "broadcast": True}).encode('utf-8')
            req = urllib.request.Request(
                f"{BACKEND_API_URL}/api/clipboard",
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                res = json.loads(response.read().decode())
                return res
        except Exception as e:
            return {"status": "error", "message": str(e)}

@mcp.tool()
def localshare_get_transfers() -> dict:
    """
    Get status of active and recent file transfers.
    """
    if HAS_DIRECT_BACKEND:
        return {"status": "success", "transfers": state.transfers}
    else:
        try:
            req = urllib.request.Request(f"{BACKEND_API_URL}/api/transfers")
            with urllib.request.urlopen(req, timeout=3) as response:
                transfers = json.loads(response.read().decode())
                return {"status": "success", "transfers": transfers}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@mcp.tool()
def localshare_toggle_approval(auto_approve: bool) -> dict:
    """
    Toggle auto-approval setting for incoming file transfers.
    """
    if HAS_DIRECT_BACKEND:
        state.auto_approve = auto_approve
        return {"status": "success", "auto_approve": state.auto_approve}
    else:
        try:
            data = json.dumps({"auto_approve": auto_approve}).encode('utf-8')
            req = urllib.request.Request(
                f"{BACKEND_API_URL}/api/config",
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=3) as response:
                res = json.loads(response.read().decode())
                return res
        except Exception as e:
            return {"status": "error", "message": str(e)}

@mcp.tool()
def localshare_delete_transfer(transfer_id: str, delete_file: bool = False) -> dict:
    """
    Delete a specific transfer record from the menu/transfers list.
    """
    if HAS_DIRECT_BACKEND:
        found_idx = None
        for idx, t in enumerate(state.transfers):
            if t.get("id") == transfer_id:
                found_idx = idx
                break
        if found_idx is not None:
            removed = state.transfers.pop(found_idx)
            return {"status": "success", "message": f"Transfer {transfer_id} removed", "removed": removed}
        return {"status": "error", "message": f"Transfer {transfer_id} not found"}
    else:
        try:
            data = json.dumps({"transfer_id": transfer_id, "delete_file": delete_file}).encode('utf-8')
            req = urllib.request.Request(
                f"{BACKEND_API_URL}/api/transfers/delete",
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=3) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            return {"status": "error", "message": str(e)}

@mcp.tool()
def localshare_clear_transfers(delete_files: bool = False) -> dict:
    """
    Clear all transfer history records from the menu list.
    """
    if HAS_DIRECT_BACKEND:
        count = len(state.transfers)
        state.transfers.clear()
        return {"status": "success", "message": f"Cleared {count} transfers"}
    else:
        try:
            data = json.dumps({"delete_files": delete_files}).encode('utf-8')
            req = urllib.request.Request(
                f"{BACKEND_API_URL}/api/transfers/clear",
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=3) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            return {"status": "error", "message": str(e)}

def run_mcp_server():
    """Run FastMCP stdio server loop."""
    print(f"🤖 Starting LocalShare FastMCP Server (Target Backend: {BACKEND_API_URL})...")
    mcp.run()

if __name__ == "__main__":
    run_mcp_server()
