"""
Clipboard Sync Module
Interfaces with macOS (pbcopy/pbpaste), Linux (xclip), Windows (powershell) and broadcasts snippets to peers.
"""

import sys
import subprocess
import shutil
from app.transfer.client import send_text_snippet

_in_memory_clipboard = ""

def get_system_clipboard() -> str:
    """Get current text from system clipboard with Wayland and X11 detection."""
    global _in_memory_clipboard
    try:
        if sys.platform == "darwin":
            return subprocess.check_output(["pbpaste"], text=True)
        elif sys.platform.startswith("linux"):
            if shutil.which("wl-paste"):
                try:
                    return subprocess.check_output(["wl-paste", "--no-newline"], text=True, timeout=1)
                except Exception:
                    pass
            if shutil.which("xclip"):
                try:
                    return subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], text=True, timeout=1)
                except Exception:
                    pass
            if shutil.which("xsel"):
                try:
                    return subprocess.check_output(["xsel", "--clipboard", "--output"], text=True, timeout=1)
                except Exception:
                    pass
            return _in_memory_clipboard
        elif sys.platform == "win32":
            out = subprocess.check_output(["powershell", "Get-Clipboard"], text=True)
            return out.strip()
    except Exception:
        pass
    return _in_memory_clipboard

def set_system_clipboard(text: str) -> bool:
    """Copy text string to system clipboard with Wayland and X11 support."""
    global _in_memory_clipboard
    if not text:
        return False
    _in_memory_clipboard = text
    try:
        if sys.platform == "darwin":
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(input=text.encode("utf-8"), timeout=2)
            return True
        elif sys.platform.startswith("linux"):
            if shutil.which("wl-copy"):
                try:
                    p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                    p.communicate(input=text.encode("utf-8"), timeout=2)
                    return True
                except Exception:
                    pass
            if shutil.which("xclip"):
                try:
                    p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                    p.communicate(input=text.encode("utf-8"), timeout=2)
                    return True
                except Exception:
                    pass
            if shutil.which("xsel"):
                try:
                    p = subprocess.Popen(["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE)
                    p.communicate(input=text.encode("utf-8"), timeout=2)
                    return True
                except Exception:
                    pass
            return True
        elif sys.platform == "win32":
            p = subprocess.Popen(["powershell", "Set-Clipboard", "-Value", f'"{text}"'])
            p.communicate(timeout=2)
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
