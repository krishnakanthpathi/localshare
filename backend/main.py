"""
LocalShare - Master Web Server & Engine (main.py)
Contains the FastAPI Web Application, REST Endpoints, UDP Discovery, and TCP Transfer Engine.
"""

import sys
import os
import time
import json
import socket
import threading
import urllib.parse
import webbrowser
from fastapi import FastAPI, UploadFile, File, Form, Response, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Ensure backend directory and localshare root are in sys.path
backend_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.abspath(os.path.join(backend_dir, ".."))
for d in [backend_dir, parent_dir]:
    if d not in sys.path:
        sys.path.insert(0, d)

try:
    from config import WEB_PORT, HOST, state
    from utils import get_network_interfaces, generate_qr_code_svg, generate_qr_code_ascii, safe_join, is_suspicious_file
    from sync.clipboard import ClipboardManager
    from discovery.udp_beacon import UDPDiscoveryServer
    from transfer.server import TCPServerEngine
    from transfer.client import TCPClientEngine
except ImportError:
    from localshare.backend.config import WEB_PORT, HOST, state
    from localshare.backend.utils import get_network_interfaces, generate_qr_code_svg, generate_qr_code_ascii, safe_join, is_suspicious_file
    from localshare.backend.sync.clipboard import ClipboardManager
    from localshare.backend.discovery.udp_beacon import UDPDiscoveryServer
    from localshare.backend.transfer.server import TCPServerEngine
    from localshare.backend.transfer.client import TCPClientEngine

# -----------------------------------------------------------------------------
# FastAPI App & Middleware Setup
# -----------------------------------------------------------------------------
app = FastAPI(title="LocalShare Web Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

udp_server_ref = None
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

# -----------------------------------------------------------------------------
# REST API & Web Routes
# -----------------------------------------------------------------------------
@app.get("/index.html")
async def serve_index():
    index_path = os.path.join(dist_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>LocalShare Server Active</h1><p>Frontend dist bundle not built yet.</p>")

@app.get("/api/config")
async def get_config():
    net_info = get_network_interfaces()
    return {
        "device_name": state.device_name,
        "upload_dir": state.upload_dir,
        "auto_approve": state.auto_approve,
        "ips": net_info["all"],
        "primary_ip": net_info["primary"],
        "tailscale": net_info["tailscale"],
        "web_url": f"http://{net_info['primary']}:{WEB_PORT}"
    }

@app.post("/api/config")
async def update_config(request: Request):
    data = await request.json()
    if "auto_approve" in data:
        state.auto_approve = bool(data["auto_approve"])
    if "upload_dir" in data and data["upload_dir"]:
        state.upload_dir = data["upload_dir"]
        os.makedirs(state.upload_dir, exist_ok=True)
    return {"status": "success", "auto_approve": state.auto_approve, "upload_dir": state.upload_dir}

@app.post("/api/clear_memory")
async def clear_memory_endpoint():
    state.clear_memory()
    return {"status": "success", "message": "In-memory transfer cache purged and garbage collector executed."}

@app.get("/api/peers")
async def get_peers():
    if udp_server_ref:
        return udp_server_ref.get_active_peers()
    return []

@app.get("/api/qrcode")
async def get_qrcode():
    net_info = get_network_interfaces()
    url = f"http://{net_info['primary']}:{WEB_PORT}"
    svg = generate_qr_code_svg(url)
    return Response(content=svg, media_type="image/svg+xml")

@app.get("/api/transfers")
async def get_transfers():
    return state.transfers

@app.post("/api/transfers/cancel")
async def cancel_transfer(request: Request):
    data = await request.json()
    tid = data.get("transfer_id")
    for t in state.transfers:
        if t["id"] == tid:
            t["status"] = "CANCELLED"
            t["speed"] = 0
            return {"status": "success", "message": f"Transfer {tid} cancelled"}
    return {"status": "error", "message": "Transfer not found"}

@app.delete("/api/transfers/{transfer_id}")
@app.post("/api/transfers/delete")
async def delete_transfer(transfer_id: str = None, request: Request = None, delete_file: bool = False):
    tid = transfer_id
    remove_disk_file = delete_file
    if request:
        try:
            body = await request.json()
            if not tid:
                tid = body.get("transfer_id")
            if "delete_file" in body:
                remove_disk_file = bool(body["delete_file"])
        except Exception:
            pass

    if not tid:
        raise HTTPException(status_code=400, detail="Missing transfer_id")

    found_idx = None
    target_transfer = None
    for idx, t in enumerate(state.transfers):
        if t.get("id") == tid:
            found_idx = idx
            target_transfer = t
            break

    if found_idx is None:
        return {"status": "error", "message": f"Transfer {tid} not found"}

    removed_item = state.transfers.pop(found_idx)
    file_deleted = False

    if remove_disk_file and "filepath" in removed_item and removed_item["filepath"]:
        try:
            abs_fp = os.path.abspath(removed_item["filepath"])
            abs_upload = os.path.abspath(state.upload_dir)
            if abs_fp.startswith(abs_upload) and os.path.exists(abs_fp):
                if os.path.isfile(abs_fp):
                    os.remove(abs_fp)
                    file_deleted = True
                elif os.path.isdir(abs_fp):
                    import shutil
                    shutil.rmtree(abs_fp)
                    file_deleted = True
        except Exception as e:
            print(f"⚠️ Error removing disk file: {e}")

    return {
        "status": "success",
        "message": f"Transfer {tid} deleted from menu",
        "transfer_id": tid,
        "file_deleted": file_deleted
    }

@app.delete("/api/transfers")
@app.post("/api/transfers/clear")
async def clear_all_transfers(request: Request = None):
    delete_files = False
    if request:
        try:
            body = await request.json()
            delete_files = bool(body.get("delete_files", False))
        except Exception:
            pass

    cleared_count = len(state.transfers)
    if delete_files:
        for item in state.transfers:
            fp = item.get("filepath")
            if fp and os.path.exists(fp):
                try:
                    abs_fp = os.path.abspath(fp)
                    abs_upload = os.path.abspath(state.upload_dir)
                    if abs_fp.startswith(abs_upload):
                        if os.path.isfile(abs_fp):
                            os.remove(abs_fp)
                        elif os.path.isdir(abs_fp):
                            import shutil
                            shutil.rmtree(abs_fp)
                except Exception as e:
                    print(f"⚠️ Error deleting disk file on clear: {e}")

    state.transfers.clear()
    return {"status": "success", "message": f"Cleared {cleared_count} transfer(s) from menu", "count": cleared_count}

@app.post("/api/shutdown")
async def shutdown_server():
    def _delayed_exit():
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=_delayed_exit, daemon=True).start()
    return {"status": "success", "message": "LocalShare node shutting down..."}

@app.get("/api/clipboard")
async def get_clipboard():
    return {
        "current": ClipboardManager.get_system_clipboard(),
        "history": state.clipboard_history
    }

@app.post("/api/clipboard")
async def update_clipboard(request: Request):
    data = await request.json()
    text = data.get("text", "")
    broadcast = data.get("broadcast", False)

    ClipboardManager.set_system_clipboard(text)
    state.clipboard_history.insert(0, {
        "timestamp": time.time(),
        "text": text,
        "sender": "web_ui"
    })

    if broadcast and udp_server_ref:
        active_peers = udp_server_ref.get_active_peers()
        for p in active_peers:
            threading.Thread(
                target=TCPClientEngine.send_text,
                args=(p["ip"], text),
                daemon=True
            ).start()

    return {"status": "success", "text": text}

@app.get("/api/pending")
async def get_pending_approvals():
    pending = []
    for tid, item in list(state.pending_approvals.items()):
        pending.append({
            "transfer_id": tid,
            "filename": item["filename"],
            "filesize": item["filesize"],
            "sender_ip": item["sender_ip"],
            "suspicious": item.get("suspicious", False)
        })
    return pending

@app.post("/api/approve")
async def respond_approval(request: Request):
    data = await request.json()
    transfer_id = data.get("transfer_id")
    action = data.get("action")

    if transfer_id in state.pending_approvals:
        item = state.pending_approvals[transfer_id]
        item["status"] = action
        item["event"].set()
        return {"status": "success", "action": action}
    raise HTTPException(status_code=404, detail="Pending transfer not found")

@app.post("/api/upload")
async def handle_upload(
    file: list[UploadFile] = File(...),
    transfer_id: str = Form(None),
    rel_path: str = Form(None),
    request: Request = None
):
    files_saved = []
    os.makedirs(state.upload_dir, exist_ok=True)
    sender_ip = request.client.host if request else "127.0.0.1"

    if request:
        if not transfer_id and "transfer_id" in request.query_params:
            transfer_id = request.query_params["transfer_id"]
        if not rel_path and "rel_path" in request.query_params:
            rel_path = request.query_params["rel_path"]

    for uploaded_file in file:
        if uploaded_file.filename:
            rel_name = rel_path or uploaded_file.filename
            save_path = safe_join(state.upload_dir, rel_name)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            tid = transfer_id or f"up_{int(time.time() * 1000)}"
            file_size = uploaded_file.size or 0

            existing = next((t for t in state.transfers if t["id"] == tid), None)
            if existing:
                transfer_record = existing
                transfer_record["status"] = "UPLOADING"
            else:
                transfer_record = {
                    "id": tid,
                    "filename": os.path.basename(rel_name),
                    "rel_path": rel_name,
                    "filepath": save_path,
                    "total_bytes": file_size,
                    "received_bytes": 0,
                    "sender_ip": sender_ip,
                    "status": "UPLOADING",
                    "start_time": time.time(),
                    "speed": 0
                }
                state.transfers.insert(0, transfer_record)

            received = 0
            start_t = time.time()
            with open(save_path, "wb") as f:
                while True:
                    chunk = await uploaded_file.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    transfer_record["received_bytes"] = received
                    if file_size == 0:
                        transfer_record["total_bytes"] = received
                    elapsed = max(time.time() - start_t, 0.001)
                    transfer_record["speed"] = received / elapsed

            transfer_record["status"] = "COMPLETED"
            transfer_record["received_bytes"] = received
            transfer_record["total_bytes"] = received
            files_saved.append(rel_name)

    return {"status": "success", "files": files_saved}

@app.get("/api/download/{rel_path:path}")
async def download_file(rel_path: str):
    try:
        abs_path = safe_join(state.upload_dir, urllib.parse.unquote(rel_path))
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Path Not Found")

        if os.path.isfile(abs_path):
            return FileResponse(abs_path, filename=os.path.basename(abs_path))
        elif os.path.isdir(abs_path):
            import shutil
            import tempfile
            folder_name = os.path.basename(abs_path.rstrip("/\\")) or "folder"
            temp_dir = tempfile.mkdtemp()
            zip_base = os.path.join(temp_dir, folder_name)
            archive_path = shutil.make_archive(zip_base, 'zip', abs_path)
            return FileResponse(
                archive_path,
                filename=f"{folder_name}.zip",
                media_type="application/zip"
            )
        raise HTTPException(status_code=400, detail="Invalid Path")
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Access Denied: {e}")

# Mount Static React Bundle
assets_dir = os.path.join(dist_dir, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

if os.path.exists(dist_dir):
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")

# -----------------------------------------------------------------------------
# Server Manager Class & Startup Engine
# -----------------------------------------------------------------------------
class WebServerManager:
    def __init__(self, port=WEB_PORT, udp_server=None, open_browser=True):
        self.port = port
        self.udp_server = udp_server
        self.open_browser = open_browser
        self.server = None
        global udp_server_ref
        udp_server_ref = udp_server

    def start(self):
        """Start Uvicorn FastAPI web server in a daemon background thread with port fallback."""
        attempts = 0
        server_started = False

        while not server_started and attempts < 10:
            current_port = self.port + attempts
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", current_port))
                self.port = current_port
                
                config = uvicorn.Config(
                    app=app,
                    log_level="warning"
                )
                self.server = uvicorn.Server(config)
                
                def _run_server():
                    try:
                        self.server.run(sockets=[sock])
                    except Exception as e:
                        print(f"⚠️ Uvicorn run error: {e}")

                t = threading.Thread(target=_run_server, daemon=True)
                t.start()
                server_started = True

                print(f"🌐 FastAPI Web Client active at: http://{get_network_interfaces()['primary']}:{current_port}")

                if self.open_browser:
                    def _open():
                        time.sleep(1.0)
                        webbrowser.open(f"http://localhost:{current_port}")
                    threading.Thread(target=_open, daemon=True).start()

            except OSError:
                sock.close()
                attempts += 1

    def stop(self):
        if self.server:
            self.server.should_exit = True

def print_banner(net_info):
    """Print ASCII banner and connection info."""
    print("=" * 64)
    print("  🚀 LocalShare - High-Speed Mesh File & Text Sharing")
    print("=" * 64)
    print(f" 💻 Device Name   : {state.device_name}")
    print(f" 🌐 Primary LAN IP : {net_info['primary']}")
    if net_info.get("tailscale"):
        print(f" 🔒 Tailscale IP   : {net_info['tailscale']}")
    print(f" 📁 Upload Folder : {os.path.abspath(state.upload_dir)}")
    print(f" 📱 Web UI URL    : http://{net_info['primary']}:{WEB_PORT}")
    print("=" * 64)

    web_url = f"http://{net_info['primary']}:{WEB_PORT}"
    print(generate_qr_code_ascii(web_url))
    print("=" * 64)

def run_main_server():
    """Main Entry Point - Launches UDP discovery, TCP file engine, and FastAPI Web Application."""
    net_info = get_network_interfaces()
    print_banner(net_info)

    udp_server = UDPDiscoveryServer()
    udp_server.start()

    tcp_server = TCPServerEngine()
    tcp_server.start()

    web_server = WebServerManager(udp_server=udp_server, open_browser=True)
    web_server.start()

    print(f"\n🟢 LocalShare Server running at: http://{net_info['primary']}:{web_server.port}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down LocalShare...")
        udp_server.stop()
        tcp_server.stop()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "cli":
        from localshare.ui.cli import run_cli
        run_cli()
    else:
        run_main_server()
