"""
LocalShare Input Subsystem (Virtual KVM Mouse / Keyboard over LAN)
"""

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
