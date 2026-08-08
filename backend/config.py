"""
LocalShare Configuration Module
"""

import os
import socket

# Load .env if present
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

# Host & Ports
HOST = os.getenv("HOST", "0.0.0.0")
UDP_PORT = int(os.getenv("UDP_PORT", "41234"))
TCP_PORT = int(os.getenv("TCP_PORT", "4001"))   # Binary TCP socket transfer port
WEB_PORT = int(os.getenv("WEB_PORT", os.getenv("PORT", "4000")))  # FastAPI HTTP Web UI & REST API port

# Transfer Buffer Settings
BUFFER_SIZE = int(os.getenv("BUFFER_SIZE", str(64 * 1024)))  # 64 KB chunk size for socket reads
PARALLEL_STREAMS_THRESHOLD = 10 * 1024 * 1024  # Use multi-socket for files > 10MB
PARALLEL_STREAMS_COUNT = 4  # 4 parallel sockets for fast transfers

# Directories
DEFAULT_UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.expanduser("~"), "Downloads", "LocalShare"))

# Discovery Settings
DISCOVERY_INTERVAL = float(os.getenv("DISCOVERY_INTERVAL", "3"))  # Seconds
DISCOVERY_TIMEOUT = float(os.getenv("DISCOVERY_TIMEOUT", "2"))   # Seconds

# Security Rules
SUSPICIOUS_EXTENSIONS = {
    ".exe", ".scr", ".bat", ".cmd", ".sh", ".vbs", ".ps1", ".apk", ".msi", ".dll", ".so", ".dylib"
}

COMPRESSIBLE_EXTENSIONS = {
    ".txt", ".json", ".xml", ".html", ".css", ".js", ".py", ".c", ".cpp", ".h", ".java",
    ".md", ".log", ".csv", ".tsv", ".svg", ".pdf", ".doc", ".docx", ".xls", ".xlsx"
}

# Runtime App State
class AppState:
    def __init__(self):
        self.upload_dir = DEFAULT_UPLOAD_DIR
        self.auto_approve = True  # Auto approve incoming files by default
        self.device_name = socket.gethostname()
        self.transfers = []
        self.clipboard_history = []
        self.pending_approvals = {}  # transfer_id -> metadata dict

    def clear_memory(self):
        """Purge in-memory logs and invoke Python Garbage Collector to free RAM."""
        self.transfers.clear()
        self.clipboard_history.clear()
        self.pending_approvals.clear()
        import gc
        gc.collect()

# Global state instance
state = AppState()
