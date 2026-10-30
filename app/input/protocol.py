"""
Binary Input Streaming Protocol for LocalShare Virtual KVM.
Ultra-lightweight 6-byte UDP packets with zero JSON overhead.
"""

import struct
from app.config import INPUT_PORT

DEFAULT_INPUT_PORT = INPUT_PORT

MAGIC_BYTE = 0x4D  # 'M' for Mouse/Movement
PACKET_FORMAT = "!BBhh"
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)  # exactly 6 bytes

# Event Types
EV_MOVE = 1    # val1 = dx, val2 = dy
EV_CLICK = 2   # val1 = button_id (1: left, 2: right, 3: middle), val2 = pressed (1: down, 0: up)
EV_SCROLL = 3  # val1 = dx, val2 = dy
EV_SWITCH = 4  # val1 = mode (1: enter remote, 0: return local), val2 = norm_y (0-1000)
EV_PING = 5    # Heartbeat request
EV_PONG = 6    # Heartbeat response

BTN_LEFT = 1
BTN_RIGHT = 2
BTN_MIDDLE = 3

def pack_packet(ev_type: int, val1: int, val2: int) -> bytes:
    """Pack an event into a 6-byte binary payload."""
    val1 = max(-32768, min(32767, int(val1)))
    val2 = max(-32768, min(32767, int(val2)))
    return struct.pack(PACKET_FORMAT, MAGIC_BYTE, ev_type, val1, val2)

def unpack_packet(data: bytes):
    """
    Unpack 6-byte binary payload.
    Returns (ev_type, val1, val2) or None if invalid.
    """
    if len(data) != PACKET_SIZE:
        return None
    try:
        magic, ev_type, val1, val2 = struct.unpack(PACKET_FORMAT, data)
        if magic != MAGIC_BYTE:
            return None
        return ev_type, val1, val2
    except struct.error:
        return None
