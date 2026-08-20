"""
REST API Endpoints for LocalShare
Settings panel, multi-folder queueing, real-time Tailscale/LAN peers, transfers, and security controls.
"""

import os
import time
import uuid
import json
import asyncio
import urllib.parse
import threading
import shutil
import tempfile
from fastapi import APIRouter, Request, UploadFile, File, Form, Response, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from app.config import state, WEB_PORT
from app.utils import get_network_interfaces, generate_qr_code_svg, safe_join
from app.db.mongo import (
    load_settings, save_settings, get_settings_dict,
    get_peer_alias, set_peer_alias, delete_peer_alias, get_all_peer_aliases,
    get_transfer_history, clear_transfer_history, record_transfer,
    save_clipboard_item, get_clipboard_history
)
from app.security.encryption import generate_key
from app.discovery.tailscale import get_tailscale_status, get_tailscale_peers
from app.discovery.udp_beacon import discover_peers
from app.queue.manager import queue_manager
from app.sync.clipboard import get_system_clipboard, set_system_clipboard, broadcast_text

api_router = APIRouter(prefix="/api")

# -----------------------------------------------------------------------------
# Real-Time Event Stream (SSE)
# -----------------------------------------------------------------------------
@api_router.get("/events")
async def sse_events(request: Request):
    """Server-Sent Events (SSE) stream for real-time transfer progress and peer discovery."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            payload = {
                "timestamp": time.time(),
                "transfers": state.transfers,
                "batches": queue_manager.get_all_batches()
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# -----------------------------------------------------------------------------
# Settings Panel Endpoints
# -----------------------------------------------------------------------------
@api_router.get("/settings")
async def fetch_settings():
    """Retrieve full settings from MongoDB / runtime state."""
    net_info = get_network_interfaces()
    settings_data = get_settings_dict()
    settings_data.update({
        "primary_ip": net_info["primary"],
        "ips": net_info["all"],
        "tailscale_ip": net_info["tailscale"],
        "web_url": f"http://{net_info['primary']}:{WEB_PORT}"
    })
    return settings_data

@api_router.post("/settings")
async def update_settings(request: Request):
    """Update settings in MongoDB and sync runtime state."""
    data = await request.json()
    saved = save_settings(data)
    return {"status": "success", "settings": saved}

@api_router.post("/settings/encryption/generate-key")
async def generate_new_encryption_key():
    """Generate a new AES-256 key for encryption."""
    new_key = generate_key()
    return {"status": "success", "key": new_key}

@api_router.get("/settings/peers")
async def list_peer_aliases():
    """Get all saved custom peer names/aliases from MongoDB."""
    return get_all_peer_aliases()

@api_router.post("/settings/peers")
async def create_or_update_peer_alias(request: Request):
    """Set custom name/alias for an IP in MongoDB."""
    data = await request.json()
    ip = data.get("ip")
    name = data.get("name")
    notes = data.get("notes", "")
    if not ip or not name:
        raise HTTPException(status_code=400, detail="Missing required 'ip' or 'name' field.")
    
    ok = set_peer_alias(ip, name, notes)
    return {"status": "success" if ok else "warning", "ip": ip, "name": name}

@api_router.delete("/settings/peers/{ip}")
async def remove_peer_alias(ip: str):
    """Delete custom peer alias from MongoDB."""
    deleted = delete_peer_alias(ip)
    return {"status": "success" if deleted else "not_found", "ip": ip}

# -----------------------------------------------------------------------------
# Multi-Folder Queue Endpoints
# -----------------------------------------------------------------------------
@api_router.get("/queue")
async def get_queue_batches():
    """Get all queued, in-progress, and recent multi-folder batch tasks."""
    return queue_manager.get_all_batches()

@api_router.post("/queue/enqueue")
async def enqueue_transfer_batch(request: Request):
    """Enqueue multiple folder paths and files to a target IP."""
    data = await request.json()
    target_ip = data.get("target_ip")
    paths = data.get("paths", [])
    target_name = data.get("target_name", "")
    encrypt = data.get("encrypt")
    compress = data.get("compress")

    if not target_ip or not paths:
        raise HTTPException(status_code=400, detail="Missing 'target_ip' or 'paths' array.")

    batch = queue_manager.enqueue_paths(
        target_ip=target_ip,
        paths=paths,
        target_name=target_name,
        encrypt=encrypt,
        compress=compress
    )
    return {"status": "success", "batch": batch.to_dict()}

@api_router.post("/queue/cancel")
async def cancel_queue_batch(request: Request):
    data = await request.json()
    bid = data.get("batch_id")
    ok = queue_manager.cancel_batch(bid)
    return {"status": "success" if ok else "error", "batch_id": bid}

@api_router.post("/queue/pause")
async def pause_queue_batch(request: Request):
    data = await request.json()
    bid = data.get("batch_id")
    ok = queue_manager.pause_batch(bid)
    return {"status": "success" if ok else "error", "batch_id": bid}

@api_router.post("/queue/resume")
async def resume_queue_batch(request: Request):
    data = await request.json()
    bid = data.get("batch_id")
    ok = queue_manager.resume_batch(bid)
    return {"status": "success" if ok else "error", "batch_id": bid}

@api_router.post("/queue/clear")
async def clear_queue_batches():
    count = queue_manager.clear_completed()
    return {"status": "success", "cleared_count": count}

# -----------------------------------------------------------------------------
# Discovery & Tailscale Endpoints
# -----------------------------------------------------------------------------
@api_router.get("/peers")
async def get_discovered_peers():
    """Return unified list of discovered LAN & Tailscale peers with custom names."""
    return discover_peers(timeout=1.5)

@api_router.get("/tailscale/status")
async def fetch_tailscale_status():
    """Get real-time Tailscale network diagnostics."""
    return get_tailscale_status()

@api_router.get("/tailscale/peers")
async def fetch_tailscale_peers():
    """Get list of active online Tailscale peers with resolved friendly names."""
    return get_tailscale_peers()

# -----------------------------------------------------------------------------
# Transfers & History Endpoints
# -----------------------------------------------------------------------------
@api_router.get("/transfers")
async def list_transfers():
    """List active in-memory transfers and historical records from MongoDB."""
    history = get_transfer_history(limit=30)
    return {
        "active": state.transfers,
        "history": history
    }

@api_router.post("/transfers/delete")
async def delete_single_transfer(request: Request):
    data = await request.json()
    tid = data.get("transfer_id")
    found_idx = next((i for i, t in enumerate(state.transfers) if t.get("id") == tid), None)
    if found_idx is not None:
        state.transfers.pop(found_idx)
        return {"status": "success", "message": f"Transfer {tid} removed."}
    return {"status": "error", "message": f"Transfer {tid} not found."}

@api_router.post("/transfers/clear")
async def clear_all_transfers_history():
    state.transfers.clear()
    cleared_db = clear_transfer_history()
    return {"status": "success", "cleared_db_count": cleared_db}

# -----------------------------------------------------------------------------
# Clipboard & Text Sync
# -----------------------------------------------------------------------------
@api_router.get("/clipboard")
async def fetch_clipboard():
    return {
        "current": get_system_clipboard(),
        "history": state.clipboard_history or get_clipboard_history(limit=20)
    }

@api_router.post("/clipboard")
async def post_clipboard(request: Request):
    data = await request.json()
    text = data.get("text", "")
    broadcast = data.get("broadcast", False)
    encrypt = data.get("encrypt", state.encryption_enabled)

    set_system_clipboard(text)
    save_clipboard_item(text, sender="web_api")
    state.clipboard_history.insert(0, {
        "timestamp": time.time(),
        "text": text,
        "sender": "web_api",
        "encrypted": encrypt
    })

    broadcast_count = 0
    if broadcast:
        peers = discover_peers(timeout=1.0)
        broadcast_count = broadcast_text(text, peers, encrypt=encrypt)

    return {"status": "success", "text": text, "broadcast_count": broadcast_count}

# -----------------------------------------------------------------------------
# Approvals & Uploads
# -----------------------------------------------------------------------------
@api_router.get("/pending")
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

@api_router.post("/approve")
async def respond_to_approval(request: Request):
    data = await request.json()
    transfer_id = data.get("transfer_id")
    action = data.get("action")

    if transfer_id in state.pending_approvals:
        item = state.pending_approvals[transfer_id]
        item["status"] = action
        item["event"].set()
        return {"status": "success", "action": action}
    raise HTTPException(status_code=404, detail="Pending transfer not found")

@api_router.post("/upload")
async def upload_files(
    file: list[UploadFile] = File(...),
    transfer_id: str = Form(None),
    rel_path: str = Form(None),
    request: Request = None
):
    files_saved = []
    os.makedirs(state.upload_dir, exist_ok=True)
    sender_ip = request.client.host if request and request.client else "127.0.0.1"

    for uploaded_file in file:
        if uploaded_file.filename:
            rel_name = rel_path or uploaded_file.filename
            save_path = safe_join(state.upload_dir, rel_name)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            t_id = transfer_id or str(uuid.uuid4())
            file_size = getattr(uploaded_file, "size", None)
            if file_size is None and request:
                content_len = request.headers.get("content-length")
                if content_len and content_len.isdigit():
                    file_size = int(content_len)
            file_size = file_size or 0

            start_t = time.time()
            transfer_rec = {
                "id": t_id,
                "filename": uploaded_file.filename,
                "rel_path": rel_name,
                "filepath": save_path,
                "total_bytes": file_size,
                "received_bytes": 0,
                "transferred_bytes": 0,
                "progress_percent": 0.0,
                "direction": "INBOUND",
                "sender_ip": sender_ip,
                "status": "IN_PROGRESS",
                "encrypted": False,
                "compressed": False,
                "speed": 0.0,
                "speed_mb": 0.0,
                "eta": 0.0,
                "start_time": start_t,
                "end_time": 0.0
            }
            state.transfers.insert(0, transfer_rec)

            try:
                received_bytes = 0
                with open(save_path, "wb") as f:
                    while True:
                        chunk = await uploaded_file.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        received_bytes += len(chunk)

                        elapsed = max(time.time() - start_t, 0.001)
                        speed = received_bytes / elapsed
                        total_for_pct = file_size if file_size >= received_bytes else received_bytes
                        pct = (received_bytes / total_for_pct * 100) if total_for_pct > 0 else 100.0
                        remaining = max(total_for_pct - received_bytes, 0)
                        eta = (remaining / speed) if speed > 0 else 0.0

                        transfer_rec["received_bytes"] = received_bytes
                        transfer_rec["transferred_bytes"] = received_bytes
                        transfer_rec["total_bytes"] = max(file_size, received_bytes)
                        transfer_rec["progress_percent"] = round(min(pct, 100.0), 1)
                        transfer_rec["speed"] = round(speed, 2)
                        transfer_rec["speed_mb"] = round(speed / (1024 * 1024), 2)
                        transfer_rec["eta"] = round(eta, 1)

                transfer_rec["status"] = "COMPLETED"
                transfer_rec["progress_percent"] = 100.0
                transfer_rec["speed"] = 0.0
                transfer_rec["eta"] = 0.0
                transfer_rec["end_time"] = time.time()
                record_transfer(transfer_rec)
                files_saved.append(rel_name)
            except Exception as e:
                transfer_rec["status"] = "FAILED"
                transfer_rec["error_message"] = str(e)
                transfer_rec["end_time"] = time.time()
                raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    return {"status": "success", "files": files_saved}

@api_router.get("/download/{rel_path:path}")
async def download_file(rel_path: str):
    try:
        abs_path = safe_join(state.upload_dir, urllib.parse.unquote(rel_path))
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Path Not Found")

        if os.path.isfile(abs_path):
            return FileResponse(abs_path, filename=os.path.basename(abs_path))
        elif os.path.isdir(abs_path):
            folder_name = os.path.basename(abs_path.rstrip("/\\")) or "folder"
            temp_dir = tempfile.mkdtemp()
            zip_base = os.path.join(temp_dir, folder_name)
            archive_path = shutil.make_archive(zip_base, 'zip', abs_path)
            return FileResponse(archive_path, filename=f"{folder_name}.zip", media_type="application/zip")
        raise HTTPException(status_code=400, detail="Invalid Path")
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Access Denied: {e}")

@api_router.get("/qrcode")
async def get_qrcode():
    net_info = get_network_interfaces()
    url = f"http://{net_info['primary']}:{WEB_PORT}"
    svg = generate_qr_code_svg(url)
    return Response(content=svg, media_type="image/svg+xml")

@api_router.post("/clear_memory")
async def clear_memory_endpoint():
    state.clear_memory()
    return {"status": "success", "message": "In-memory cache purged and garbage collector executed."}

@api_router.post("/shutdown")
async def shutdown_node():
    def _delayed():
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=_delayed, daemon=True).start()
    return {"status": "success", "message": "LocalShare node shutting down..."}
