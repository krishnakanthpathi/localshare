"""
Clipboard Sync Module
Interfaces with macOS (pbcopy/pbpaste), Linux (xclip), Windows (powershell) and broadcasts snippets to peers.
"""

import sys
import subprocess
from app.transfer.client import send_text_snippet

def get_system_clipboard() -> str:
    """Get current text from system clipboard."""
    try:
        if sys.platform == "darwin":
            out = subprocess.check_output(["pbpaste"], text=True)
            return out
        elif sys.platform.startswith("linux"):
            out = subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], text=True)
            return out
        elif sys.platform == "win32":
            out = subprocess.check_output(["powershell", "Get-Clipboard"], text=True)
            return out.strip()
    except Exception:
        pass
    return ""

def set_system_clipboard(text: str) -> bool:
    """Copy text string to system clipboard."""
    if not text:
        return False
    try:
        if sys.platform == "darwin":
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            return True
        elif sys.platform.startswith("linux"):
            p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"))
            return True
        elif sys.platform == "win32":
            p = subprocess.Popen(["powershell", "Set-Clipboard", "-Value", f'"{text}"'])
            p.communicate()
            return True
    except Exception:
        pass
    return False

def broadcast_text(text: str, peers: list[dict], encrypt: bool = None) -> int:
    """Broadcast text snippet to all active peers on LAN and Tailscale."""
    if not text or not peers:
        return 0
    
    sent_count = 0
    for peer in peers:
        ip = peer.get("ip")
        port = peer.get("port", 4001)
        if ip:
            ok, _ = send_text_snippet(ip, text, target_port=port, encrypt=encrypt)
            if ok:
                sent_count += 1
                
    return sent_count
