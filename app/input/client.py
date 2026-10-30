"""
LocalShare Virtual KVM - Mouse Client Engine (Linux / Windows Receiver)
Listens for low-latency UDP packets, simulates cursor movement and clicks,
and detects edge pushback to return control to the host machine.
"""

import os
import sys
import glob
import time
import socket
import subprocess
from typing import Optional

# Ensure Linux / Wayland / Xwayland display variables are populated even in headless / SSH sessions
if sys.platform.startswith("linux"):
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    if "XDG_RUNTIME_DIR" not in os.environ and os.path.exists(f"/run/user/{uid}"):
        os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    if "XAUTHORITY" not in os.environ:
        auths = sorted(glob.glob(f"/run/user/{uid}/.mutter-Xwaylandauth.*"), key=os.path.getmtime, reverse=True)
        if not auths and os.path.exists(os.path.expanduser("~/.Xauthority")):
            auths = [os.path.expanduser("~/.Xauthority")]
        if auths:
            os.environ["XAUTHORITY"] = auths[0]
    if "DISPLAY" not in os.environ:
        os.environ["DISPLAY"] = ":0"

from pynput.mouse import Controller as MouseController, Button

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
    """Detect display resolution on Linux, Windows, or macOS."""
    # 1. Windows native
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
        except Exception:
            pass

    # 2. macOS native
    if sys.platform == "darwin":
        try:
            from AppKit import NSScreen
            frame = NSScreen.mainScreen().frame()
            return int(frame.size.width), int(frame.size.height)
        except Exception:
            pass

    # 3. Linux xrandr / Xlib check
    if sys.platform.startswith("linux"):
        try:
            import re
            out = subprocess.check_output(["xrandr"], stderr=subprocess.DEVNULL, text=True)
            m = re.search(r"current\s+(\d+)\s+x\s+(\d+)", out)
            if m:
                return int(m.group(1)), int(m.group(2))
            for line in out.splitlines():
                if " connected" in line and ("primary" in line or "+" in line):
                    for part in line.split():
                        if "x" in part and "+" in part:
                            res = part.split("+")[0].split("x")
                            return int(res[0]), int(res[1])
        except Exception:
            pass

        try:
            from Xlib import display
            d = display.Display()
            s = d.screen()
            return int(s.width_in_pixels), int(s.height_in_pixels)
        except Exception:
            pass

    # 4. Tkinter fallback (Cross-platform)
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


class MouseClient:
    def __init__(
        self,
        bind_port: int = DEFAULT_INPUT_PORT,
        edge: str = "left",
        width: Optional[int] = None,
        height: Optional[int] = None
    ):
        self.bind_port = bind_port
        self.edge = edge.lower()

        # Screen dimensions
        det_w, det_h = get_screen_bounds()
        self.screen_width = width or det_w
        self.screen_height = height or det_h

        self.mouse = MouseController()
        self.active = False
        self.running = False
        self.enter_time = 0.0

        # Current virtual cursor coords
        self.cur_x = 70
        self.cur_y = self.screen_height // 2

        self.host_addr = None

        # UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", self.bind_port))

    def start(self):
        """Start UDP receiver loop."""
        self.running = True

        print("=" * 64)
        print("  🖥️  LOCALSHARE VIRTUAL KVM - MOUSE CLIENT (Receiver)")
        print("=" * 64)
        print(f" 📡 Listening on   : UDP 0.0.0.0:{self.bind_port}")
        print(f" 🖥️ Screen Size    : {self.screen_width}x{self.screen_height}")
        print(f" 🔄 Return Edge    : Push past [{self.edge.upper()}] edge to return to Mac")
        print("=" * 64)
        print("Awaiting input stream from Host machine...\n")

        try:
            while self.running:
                data, addr = self.sock.recvfrom(64)
                self.host_addr = addr

                packet = unpack_packet(data)
                if not packet:
                    continue

                ev_type, val1, val2 = packet

                # Mode Switch
                if ev_type == EV_SWITCH:
                    if val1 == 1:
                        # Enter remote
                        self.active = True
                        self.enter_time = time.time()
                        norm_y = val2
                        target_y = int((norm_y / 1000.0) * self.screen_height)
                        # Enter safely past the left sidebar / dock
                        self.cur_x = 70 if self.edge == "left" else (self.screen_width - 70)
                        self.cur_y = max(0, min(self.screen_height - 1, target_y))
                        self.mouse.position = (self.cur_x, self.cur_y)
                        sys.stdout.write(f"\r\033[K🎮 [MouseClient] Host took control at ({self.cur_x}, {self.cur_y})\n")
                        sys.stdout.flush()
                    elif val1 == 0:
                        # Exit remote
                        self.active = False
                        sys.stdout.write(f"\r\033[K⏸️  [MouseClient] Host released control.\n")
                        sys.stdout.flush()

                # Mouse Movement
                elif ev_type == EV_MOVE:
                    if not self.active:
                        self.active = True

                    dx = val1
                    dy = val2
                    next_x = self.cur_x + dx
                    next_y = self.cur_y + dy

                    # Return to Host check (cooldown to avoid jitter upon entering)
                    returned = False
                    if time.time() - self.enter_time > 0.4:
                        if self.edge == "left" and next_x <= 0 and dx < 0:
                            returned = True
                        elif self.edge == "right" and next_x >= self.screen_width - 1 and dx > 0:
                            returned = True

                    if returned:
                        self.active = False
                        norm_y = int((self.cur_y / max(1, self.screen_height)) * 1000)
                        self.sock.sendto(pack_packet(EV_SWITCH, 0, norm_y), addr)
                        sys.stdout.write(f"\r\033[K🏠 [MouseClient] Pushed off {self.edge.upper()} edge -> Returned to Host.\n")
                        sys.stdout.flush()
                        continue

                    # Clamp to local display bounds
                    self.cur_x = max(0, min(self.screen_width - 1, next_x))
                    self.cur_y = max(0, min(self.screen_height - 1, next_y))
                    self.mouse.position = (self.cur_x, self.cur_y)

                # Mouse Clicks
                elif ev_type == EV_CLICK and self.active:
                    btn_id = val1
                    pressed = (val2 == 1)

                    btn = Button.left
                    if btn_id == BTN_RIGHT:
                        btn = Button.right
                    elif btn_id == BTN_MIDDLE:
                        btn = Button.middle

                    try:
                        if pressed:
                            self.mouse.press(btn)
                        else:
                            self.mouse.release(btn)
                    except Exception:
                        pass

                # Mouse Scrolling
                elif ev_type == EV_SCROLL and self.active:
                    try:
                        self.mouse.scroll(val1, val2)
                    except Exception:
                        pass

        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """Clean shutdown."""
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        print("\n👋 Mouse Client stopped.")


def start_mouse_client(bind_port: int = DEFAULT_INPUT_PORT, edge: str = "left", width: Optional[int] = None, height: Optional[int] = None):
    client = MouseClient(bind_port=bind_port, edge=edge, width=width, height=height)
    client.start()
