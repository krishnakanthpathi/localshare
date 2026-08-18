"""
Binary Length-Prefixed Framing Protocol
"""

import json
import struct
from app.processing.stream import read_exact_bytes

HEADER_FORMAT = ">I"  # 4-byte unsigned integer (big-endian)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

def send_message(sock, data_dict: dict):
    """
    Send a length-prefixed JSON message payload over socket.
    Format: [4-byte Payload Length][JSON Payload Bytes]
    """
    json_bytes = json.dumps(data_dict).encode("utf-8")
    header = struct.pack(HEADER_FORMAT, len(json_bytes))
    sock.sendall(header + json_bytes)

def receive_message(sock) -> dict | None:
    """
    Receive a length-prefixed JSON message payload from socket.
    Returns decoded dictionary or None on connection close/error.
    """
    try:
        header_bytes = read_exact_bytes(sock, HEADER_SIZE)
        if not header_bytes:
            return None
        length = struct.unpack(HEADER_FORMAT, header_bytes)[0]
        
        payload_bytes = read_exact_bytes(sock, length)
        if not payload_bytes:
            return None
        # {"cmd": "HELLO"}
        # }{"cmd": "BYE"} 
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None
