"""
LocalShare Virtual KVM - Mouse Host Engine (Mac / Controller)
Tracks cursor movement, captures screen boundary push events, and streams
low-latency UDP binary packets to the remote client.
"""

import sys
import time
import socket
import threading
from typing import Optional

from pynput.mouse import Controller as MouseController, Listener as MouseListener, Button
from pynput.keyboard import Listener as KeyboardListener, Key

from app.config import INPUT_PORT
from app.input.protocol import (
    DEFAULT_INPUT_PORT,
    EV_MOVE,
    EV_CLICK,
    EV_SCROLL,
    EV_SWITCH,
    BTN_LEFT,
    BTN_RIGHT,
    BTN_MIDDLE,
    pack_packet,
    unpack_packet
)

def get_screen_bounds() -> tuple[int, int]:
    """Detect main display resolution across platforms."""
    if sys.platform == "darwin":
        try:
            from AppKit import NSScreen
            frame = NSScreen.mainScreen().frame()
            return int(frame.size.width), int(frame.size.height)
        except Exception:
            pass

    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        return w, h
    except Exception:
        pass

    return 1920, 1080


class MouseHost:
    def __init__(
        self,
        target_ip: str,
        target_port: int = DEFAULT_INPUT_PORT,
        local_port: int = DEFAULT_INPUT_PORT,
        edge: str = "right",
        edge_margin: int = 4
    ):
        self.target_ip = target_ip
        self.target_port = target_port
        self.local_port = local_port
        self.edge = edge.lower()
        self.edge_margin = edge_margin

        self.mouse = MouseController()
        self.screen_width, self.screen_height = get_screen_bounds()

        # State: "LOCAL" or "REMOTE"
        self.state = "LOCAL"
        self.running = False
        self.is_warping = False

        # Anchor coordinates when in REMOTE mode
        self.anchor_x = self.screen_width - 150
        self.anchor_y = self.screen_height // 2

        # UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("", self.local_port))
        except Exception:
            # Ephemeral bind if port is occupied
            self.sock.bind(("", 0))

        self.mouse_listener: Optional[MouseListener] = None
        self.keyboard_listener: Optional[KeyboardListener] = None
        self.rx_thread: Optional[threading.Thread] = None

    def _send(self, packet: bytes):
        try:
            self.sock.sendto(packet, (self.target_ip, self.target_port))
        except Exception:
            pass

    def _on_move(self, x, y):
        if not self.running:
            return

        if self.state == "LOCAL":
            # Edge push detection
            entered = False
            if self.edge == "right" and x >= self.screen_width - self.edge_margin:
                entered = True
            elif self.edge == "left" and x <= self.edge_margin:
                entered = True

            if entered:
                self.state = "REMOTE"
                norm_y = int((y / max(1, self.screen_height)) * 1000)
                self._send(pack_packet(EV_SWITCH, 1, norm_y))

                # Warp cursor to safe anchor inside screen
                self.anchor_x = self.screen_width - 150 if self.edge == "right" else 150
                self.anchor_y = int(y)
                self.is_warping = True
                self.mouse.position = (self.anchor_x, self.anchor_y)
                self.is_warping = False

                sys.stdout.write(f"\r\033[K⚡ [MouseHost] -> Switched to REMOTE ({self.target_ip}). (Press ESC to return)\n")
                sys.stdout.flush()

        elif self.state == "REMOTE":
            if self.is_warping:
                return

            dx = int(x - self.anchor_x)
            dy = int(y - self.anchor_y)

            if dx != 0 or dy != 0:
                self._send(pack_packet(EV_MOVE, dx, dy))

                # Pin cursor back to anchor
                self.is_warping = True
                self.mouse.position = (self.anchor_x, self.anchor_y)
                self.is_warping = False

    def _on_click(self, x, y, button, pressed):
        if not self.running or self.state != "REMOTE":
            return

        btn_id = BTN_LEFT
        if button == Button.right:
            btn_id = BTN_RIGHT
        elif button == Button.middle:
            btn_id = BTN_MIDDLE

        self._send(pack_packet(EV_CLICK, btn_id, 1 if pressed else 0))

    def _on_scroll(self, x, y, dx, dy):
        if not self.running or self.state != "REMOTE":
            return

        self._send(pack_packet(EV_SCROLL, int(dx), int(dy)))

    def _on_key_press(self, key):
        if not self.running:
            return

        # Emergency escape or manual switchback
        if key == Key.esc and self.state == "REMOTE":
            self.return_to_local()
            sys.stdout.write("\r\033[K🏠 [MouseHost] <- ESC pressed. Returned to LOCAL.\n")
            sys.stdout.flush()

    def return_to_local(self, norm_y: Optional[int] = None):
        """Switch state back to local host screen."""
        self.state = "LOCAL"
        self._send(pack_packet(EV_SWITCH, 0, 0))

        if norm_y is not None:
            target_y = int((norm_y / 1000.0) * self.screen_height)
        else:
            target_y = self.screen_height // 2

        return_x = self.screen_width - 30 if self.edge == "right" else 30
        self.is_warping = True
        self.mouse.position = (return_x, target_y)
        self.is_warping = False

    def _listen_incoming(self):
        """Listen for release and heartbeat signals from remote client."""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(64)
                res = unpack_packet(data)
                if not res:
                    continue

                ev_type, val1, val2 = res
                if ev_type == EV_SWITCH and val1 == 0:
                    # Client signaled cursor pushed back over edge
                    norm_y = val2
                    self.return_to_local(norm_y)
                    sys.stdout.write(f"\r\033[K🏠 [MouseHost] <- Cursor returned from REMOTE edge.\n")
                    sys.stdout.flush()
            except Exception:
                break

    def start(self):
        """Start monitoring and streaming mouse events."""
        self.running = True

        print("=" * 64)
        print("  🖱️  LOCALSHARE VIRTUAL KVM - MOUSE HOST (Active)")
        print("=" * 64)
        print(f" 🎯 Target Peer    : {self.target_ip}:{self.target_port}")
        print(f" 🖥️ Local Screen   : {self.screen_width}x{self.screen_height}")
        print(f" 🔄 Edge Switch    : Push past [{self.edge.upper()}] edge to enter Remote")
        print(f" 🛑 Emergency Exit : Press ESC anytime to force return to Mac")
        print("=" * 64)
        print("Ready. Move your cursor to the right edge of your screen...\n")

        self.rx_thread = threading.Thread(target=self._listen_incoming, daemon=True)
        self.rx_thread.start()

        self.keyboard_listener = KeyboardListener(on_press=self._on_key_press)
        self.keyboard_listener.start()

        self.mouse_listener = MouseListener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll
        )
        self.mouse_listener.start()

        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """Clean shutdown."""
        self.running = False
        if self.state == "REMOTE":
            self.return_to_local()

        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except Exception:
                pass
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception:
                pass
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        print("\n👋 Mouse Host stopped.")


def start_mouse_host(target_ip: str, target_port: int = DEFAULT_INPUT_PORT, edge: str = "right"):
    host = MouseHost(target_ip=target_ip, target_port=target_port, edge=edge)
    host.start()
