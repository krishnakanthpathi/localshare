"""
LocalShare Core Configuration Module
No .env files used - runtime configuration is dynamically managed via MongoDB and Settings Panel.
"""

import os
import socket

# Default Host & Ports
HOST = "0.0.0.0"
UDP_PORT = 41234
TCP_PORT = 4001
WEB_PORT = 4000
MCP_PORT = 8000

# Transfer Settings
BUFFER_SIZE = 512 * 1024  # 512 KB streaming chunk
SOCKET_BUFFER_SIZE = 4 * 1024 * 1024  # 4 MB high-speed TCP window buffer for Tailscale / WAN links
PARALLEL_STREAMS_THRESHOLD = 10 * 1024 * 1024  # 10 MB
DEFAULT_UPLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "LocalShare")

# Discovery Settings
DISCOVERY_INTERVAL = 3.0
DISCOVERY_TIMEOUT = 2.0

# Database Defaults
DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_MONGO_DB = "localshare"

# Security Rules
SUSPICIOUS_EXTENSIONS = {
    ".exe", ".scr", ".bat", ".cmd", ".sh", ".vbs", ".ps1", ".apk", ".msi", ".dll", ".so", ".dylib"
}

COMPRESSIBLE_EXTENSIONS = {
    ".txt", ".json", ".xml", ".html", ".css", ".js", ".py", ".c", ".cpp", ".h", ".java",
    ".md", ".log", ".csv", ".tsv", ".svg", ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".tar", ".iso", ".bin", ".dat", ".sql"
}

# Runtime App State
class AppState:
    def __init__(self):
        self.device_name = socket.gethostname()
        self.upload_dir = DEFAULT_UPLOAD_DIR
        self.auto_approve = True
        self.encryption_enabled = False
        self.encryption_key = ""  # Base64 32-byte AES key
        self.compression_enabled = True
        self.compression_level = 6
        self.mongo_uri = DEFAULT_MONGO_URI
        self.mongo_db = DEFAULT_MONGO_DB
        self.mongo_connected = False
        
        # In-memory tracking
        self.transfers = []
        self.clipboard_history = []
        self.pending_approvals = {}  # transfer_id -> dict
        self.peer_cache = {}        # ip -> peer metadata dict

    def clear_memory(self):
        """Purge in-memory transfer logs and invoke Garbage Collector."""
        self.transfers.clear()
        self.clipboard_history.clear()
        self.pending_approvals.clear()
        import gc
        gc.collect()

# Global runtime state instance
state = AppState()
