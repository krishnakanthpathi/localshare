"""
LocalShare MCP Configuration
"""

import os

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:4000")
