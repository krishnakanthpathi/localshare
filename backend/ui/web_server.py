"""
FastAPI + Uvicorn Web Server Module (Re-exported from main.py)
"""

try:
    from main import app, WebServerManager
except ImportError:
    from ..main import app, WebServerManager

__all__ = ["app", "WebServerManager"]
