"""
LocalShare Input Subsystem (Virtual KVM Mouse / Keyboard over LAN)
"""

import os
import sys
import glob

# Ensure Linux / Wayland / Xwayland display variables are populated before pynput loads
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

from app.input.protocol import (
    DEFAULT_INPUT_PORT,
    EV_MOVE,
    EV_CLICK,
    EV_SCROLL,
    EV_SWITCH,
    pack_packet,
    unpack_packet
)
from app.input.host import start_mouse_host
from app.input.client import start_mouse_client

__all__ = [
    "DEFAULT_INPUT_PORT",
    "EV_MOVE",
    "EV_CLICK",
    "EV_SCROLL",
    "EV_SWITCH",
    "pack_packet",
    "unpack_packet",
    "start_mouse_host",
    "start_mouse_client",
]
