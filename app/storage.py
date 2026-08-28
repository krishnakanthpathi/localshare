"""
LocalShare Storage & Single Log File Engine
Manages persistent local configuration (~/.localshare/config.json) and
maintains a unified, timestamped log file (~/.localshare/localshare.log).
Replaces external database dependencies with fast, zero-dependency local files.
"""

import os
import json
import time
import threading
from datetime import datetime
from app.config import state, LOCALSHARE_DIR, CONFIG_FILE, LOG_FILE, DEFAULT_UPLOAD_DIR

_lock = threading.Lock()

def _ensure_dir():
    """Ensure ~/.localshare directory exists."""
    os.makedirs(LOCALSHARE_DIR, exist_ok=True)

def log_event(level: str, message: str, metadata: dict = None):
    """
    Append a structured, timestamped log entry to ~/.localshare/localshare.log.
    Format: YYYY-MM-DD HH:MM:SS [LEVEL] Message | Metadata
    """
    _ensure_dir()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_str = f" | {json.dumps(metadata)}" if metadata else ""
    log_line = f"{now_str} [{level.upper():<5}] {message}{meta_str}\n"

    try:
        with _lock:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
    except Exception as e:
        print(f"⚠️ Log write error: {e}")

def log_info(message: str, metadata: dict = None):
    log_event("INFO", message, metadata)

def log_warning(message: str, metadata: dict = None):
    log_event("WARN", message, metadata)

def log_error(message: str, metadata: dict = None):
    log_event("ERROR", message, metadata)

# -----------------------------------------------------------------------------
# Configuration File Management (~/.localshare/config.json)
# -----------------------------------------------------------------------------
def _read_config_file() -> dict:
    _ensure_dir()
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_config_file(data: dict):
    _ensure_dir()
    with _lock:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log_error(f"Failed to write config file: {e}")

def load_settings() -> dict:
    """Load settings from ~/.localshare/config.json into runtime state."""
    cfg = _read_config_file()
    settings = cfg.get("settings", {})

    if "device_name" in settings:
        state.device_name = str(settings["device_name"])
    if "upload_dir" in settings:
        state.upload_dir = str(settings["upload_dir"])
    if "auto_approve" in settings:
        state.auto_approve = bool(settings["auto_approve"])
    if "encryption_enabled" in settings:
        state.encryption_enabled = bool(settings["encryption_enabled"])
    if "encryption_key" in settings:
        state.encryption_key = str(settings["encryption_key"])
    if "compression_enabled" in settings:
        state.compression_enabled = bool(settings["compression_enabled"])
    if "compression_level" in settings:
        state.compression_level = int(settings["compression_level"])

    return get_settings_dict()

def save_settings(settings_dict: dict) -> dict:
    """Save settings to ~/.localshare/config.json and update runtime state."""
    if "device_name" in settings_dict and settings_dict["device_name"]:
        state.device_name = str(settings_dict["device_name"])
    if "upload_dir" in settings_dict and settings_dict["upload_dir"]:
        state.upload_dir = str(settings_dict["upload_dir"])
    if "auto_approve" in settings_dict:
        state.auto_approve = bool(settings_dict["auto_approve"])
    if "encryption_enabled" in settings_dict:
        state.encryption_enabled = bool(settings_dict["encryption_enabled"])
    if "encryption_key" in settings_dict:
        state.encryption_key = str(settings_dict["encryption_key"])
    if "compression_enabled" in settings_dict:
        state.compression_enabled = bool(settings_dict["compression_enabled"])
    if "compression_level" in settings_dict:
        state.compression_level = int(settings_dict["compression_level"])

    cfg = _read_config_file()
    cfg["settings"] = {
        "device_name": state.device_name,
        "upload_dir": state.upload_dir,
        "auto_approve": state.auto_approve,
        "encryption_enabled": state.encryption_enabled,
        "encryption_key": state.encryption_key,
        "compression_enabled": state.compression_enabled,
        "compression_level": state.compression_level,
        "updated_at": time.time()
    }
    _write_config_file(cfg)
    log_info("Settings updated and saved to config file.")
    return get_settings_dict()

def get_settings_dict() -> dict:
    """Return dictionary of current settings."""
    return {
        "device_name": state.device_name,
        "upload_dir": state.upload_dir,
        "auto_approve": state.auto_approve,
        "encryption_enabled": state.encryption_enabled,
        "encryption_key": state.encryption_key,
        "compression_enabled": state.compression_enabled,
        "compression_level": state.compression_level,
        "config_file": CONFIG_FILE,
        "log_file": LOG_FILE
    }

# -----------------------------------------------------------------------------
# Peer Aliases & Custom Names
# -----------------------------------------------------------------------------
def get_peer_alias(ip: str) -> str | None:
    """Retrieve custom friendly name for an IP."""
    cfg = _read_config_file()
    aliases = cfg.get("peer_aliases", {})
    entry = aliases.get(str(ip).strip())
    if entry:
        return entry.get("name")
    return None

def set_peer_alias(ip: str, name: str, notes: str = "") -> bool:
    """Set or update custom alias for an IP in config.json."""
    clean_ip = str(ip).strip()
    clean_name = str(name).strip()
    cfg = _read_config_file()
    if "peer_aliases" not in cfg:
        cfg["peer_aliases"] = {}
    cfg["peer_aliases"][clean_ip] = {
        "ip": clean_ip,
        "name": clean_name,
        "notes": notes,
        "updated_at": time.time()
    }
    _write_config_file(cfg)
    log_info(f"Saved peer alias for {clean_ip} -> '{clean_name}'")
    return True

def delete_peer_alias(ip: str) -> bool:
    """Remove custom alias for an IP."""
    clean_ip = str(ip).strip()
    cfg = _read_config_file()
    if "peer_aliases" in cfg and clean_ip in cfg["peer_aliases"]:
        del cfg["peer_aliases"][clean_ip]
        _write_config_file(cfg)
        log_info(f"Deleted peer alias for {clean_ip}")
        return True
    return False

def get_all_peer_aliases() -> dict:
    """Return dict of all IP -> alias records."""
    cfg = _read_config_file()
    return cfg.get("peer_aliases", {})

# -----------------------------------------------------------------------------
# Transfer Logging & History
# -----------------------------------------------------------------------------
def record_transfer(transfer_data: dict):
    """Record a transfer event into localshare.log and in-memory history."""
    rec = dict(transfer_data)
    rec["timestamp"] = time.time()
    direction = rec.get("direction", "TRANSFER")
    status = rec.get("status", "COMPLETED")
    fname = rec.get("filename", "unknown")
    size_bytes = rec.get("total_bytes", 0)
    target = rec.get("target_ip") or rec.get("sender_ip") or "unknown"
    
    msg = f"[TRANSFER] {direction} {status}: '{fname}' ({size_bytes:,} bytes) with {target}"
    log_info(msg, metadata={
        "type": "TRANSFER",
        "id": rec.get("id"),
        "filename": fname,
        "bytes": size_bytes,
        "direction": direction,
        "status": status,
        "target": target,
        "speed_mb": rec.get("speed_mb", 0.0),
        "timestamp": rec["timestamp"]
    })

def get_transfer_history(limit: int = 50) -> list[dict]:
    """Retrieve recent transfer records from state and log file."""
    transfers = list(state.transfers)
    if len(transfers) >= limit:
        return transfers[:limit]

    # Fallback to reading parsed JSON transfer logs from localshare.log
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                if "[TRANSFER]" in line and " | {" in line:
                    try:
                        meta_part = line.split(" | ", 1)[1].strip()
                        meta = json.loads(meta_part)
                        if meta.get("type") == "TRANSFER" and not any(t.get("id") == meta.get("id") for t in transfers):
                            transfers.append(meta)
                            if len(transfers) >= limit:
                                break
                    except Exception:
                        continue
        except Exception:
            pass
    return transfers[:limit]

def clear_transfer_history() -> int:
    """Clear in-memory transfers."""
    count = len(state.transfers)
    state.transfers.clear()
    log_info("Cleared in-memory transfer history.")
    return count

# -----------------------------------------------------------------------------
# Clipboard Logging & History
# -----------------------------------------------------------------------------
def save_clipboard_item(text: str, sender: str = "local", sender_ip: str = "127.0.0.1"):
    """Record clipboard/text snippet to localshare.log."""
    snippet_preview = text[:80].replace("\n", " ") + ("..." if len(text) > 80 else "")
    log_info(f"[CLIPBOARD] From {sender} ({sender_ip}): \"{snippet_preview}\"", metadata={
        "type": "CLIPBOARD",
        "sender": sender,
        "sender_ip": sender_ip,
        "text": text,
        "timestamp": time.time()
    })

def get_clipboard_history(limit: int = 50) -> list[dict]:
    """Fetch clipboard history from runtime state and log file."""
    history = list(state.clipboard_history)
    if len(history) >= limit:
        return history[:limit]

    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                if "[CLIPBOARD]" in line and " | {" in line:
                    try:
                        meta_part = line.split(" | ", 1)[1].strip()
                        meta = json.loads(meta_part)
                        if meta.get("type") == "CLIPBOARD":
                            history.append(meta)
                            if len(history) >= limit:
                                break
                    except Exception:
                        continue
        except Exception:
            pass
    return history[:limit]

def get_recent_log_lines(limit: int = 40) -> list[str]:
    """Retrieve the most recent raw lines from localshare.log."""
    if not os.path.exists(LOG_FILE):
        return ["(Log file is currently empty)"]
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [l.rstrip("\n") for l in lines[-limit:]]
    except Exception as e:
        return [f"Error reading log file: {e}"]
