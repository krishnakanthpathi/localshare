"""
Transfer Protocol Module
Binary message framing, length-prefixed headers, and transfer metadata structures.
"""

import json
import struct

HEADER_FORMAT = ">I"  # 4-byte unsigned integer (big-endian)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

def send_message(sock, data_dict):
    """
    Send a length-prefixed JSON payload over socket.
    Format: [4-byte Payload Length][JSON Payload Bytes]
    """
    json_bytes = json.dumps(data_dict).encode("utf-8")
    header = struct.pack(HEADER_FORMAT, len(json_bytes))
    sock.sendall(header + json_bytes)

def receive_message(sock):
    """
    Receive a length-prefixed JSON payload from socket.
    Returns decoded dictionary or None on connection close/error.
    """
    try:
        header_bytes = _read_exact(sock, HEADER_SIZE)
        if not header_bytes:
            return None
        length = struct.unpack(HEADER_FORMAT, header_bytes)[0]
        
        payload_bytes = _read_exact(sock, length)
        if not payload_bytes:
            return None
            
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None

def _read_exact(sock, n_bytes):
    """Read exactly n_bytes from socket stream."""
    buffer = bytearray()
    while len(buffer) < n_bytes:
        chunk = sock.recv(n_bytes - len(buffer))
        if not chunk:
            return None
        buffer.extend(chunk)
    return bytes(buffer)
