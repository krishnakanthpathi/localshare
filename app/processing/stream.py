"""
Stream wrappers and socket adapters for chunk processing.
"""

from app.config import BUFFER_SIZE

class SocketReadStream:
    """Socket reader adapter exposing a standard read() interface."""
    def __init__(self, sock):
        self.sock = sock

    def read(self, size=-1):
        try:
            read_size = size if size > 0 else BUFFER_SIZE
            return self.sock.recv(read_size)
        except Exception:
            return b""

class SocketWriteStream:
    """Socket writer adapter exposing a standard write() interface."""
    def __init__(self, sock):
        self.sock = sock

    def write(self, data: bytes):
        if not data:
            return 0
        self.sock.sendall(data)
        return len(data)

    def flush(self):
        pass

def read_exact_bytes(sock, n_bytes: int) -> bytes | None:
    """Read exactly n_bytes from socket stream."""
    buffer = bytearray()
    while len(buffer) < n_bytes:
        chunk = sock.recv(n_bytes - len(buffer))
        if not chunk:
            return None
        buffer.extend(chunk)
    return bytes(buffer)
