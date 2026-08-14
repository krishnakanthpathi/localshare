"""
FastAPI Application Factory and Web Server Runner
"""

import socket
import threading
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import WEB_PORT
from app.api.routes import api_router
from app.db.mongo import load_settings

def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    # Attempt to load saved settings from MongoDB
    load_settings()

    app = FastAPI(title="LocalShare Web Engine", version="2.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app

def start_web_server(port: int = WEB_PORT, open_browser: bool = False) -> tuple[uvicorn.Server | None, int]:
    """Start Uvicorn web server in a daemon background thread with port fallback."""
    fastapi_app = create_app()
    attempts = 0
    server = None
    final_port = port

    while attempts < 10:
        current_port = port + attempts
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", current_port))
            final_port = current_port
            
            config = uvicorn.Config(
                app=fastapi_app,
                log_level="warning"
            )
            server = uvicorn.Server(config)
            
            def _run():
                try:
                    server.run(sockets=[sock])
                except Exception as e:
                    print(f"⚠️ Uvicorn run error: {e}")

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            break
        except OSError:
            sock.close()
            attempts += 1

    return server, final_port
