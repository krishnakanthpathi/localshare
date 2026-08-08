"""
Clipboard & Text Sync Module
Interfaces with OS clipboard (macOS pbcopy/pbpaste, Linux xclip, Windows powershell) and broadcasts text snippets across peers.
"""

import sys
import subprocess
try:
    from config import state
    from transfer.client import TCPClientEngine
except ImportError:
    from ..config import state
    from ..transfer.client import TCPClientEngine

class ClipboardManager:
    @staticmethod
    def get_system_clipboard():
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

    @staticmethod
    def set_system_clipboard(text):
        """Copy text string to system clipboard."""
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

    @staticmethod
    def broadcast_text(text, peers):
        """Broadcast text snippet to all active peers on network."""
        if not text or not peers:
            return 0
        
        sent_count = 0
        for peer in peers:
            ip = peer.get("ip")
            port = peer.get("port", 4000)
            ok, _ = TCPClientEngine.send_text_snippet(ip, text, target_port=port)
            if ok:
                sent_count += 1
                
        return sent_count
