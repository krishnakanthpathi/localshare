"""
MongoDB Persistence Engine for LocalShare
Handles settings, peer aliases/names, transfer logs, and clipboard history.
"""

import time
import pymongo
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from app.config import state, DEFAULT_MONGO_URI, DEFAULT_MONGO_DB, DEFAULT_UPLOAD_DIR

_client = None

def get_client(uri=None):
    """Get or create singleton PyMongo client."""
    global _client
    target_uri = uri or state.mongo_uri or DEFAULT_MONGO_URI
    if _client is None:
        try:
            _client = pymongo.MongoClient(target_uri, serverSelectionTimeoutMS=2000)
            # Trigger quick ping
            _client.admin.command("ping")
            state.mongo_connected = True
        except Exception:
            state.mongo_connected = False
            return None
    return _client

def get_db(uri=None, db_name=None):
    """Get MongoDB database instance."""
    client = get_client(uri)
    if client is None:
        return None
    name = db_name or state.mongo_db or DEFAULT_MONGO_DB
    return client[name]

def is_connected():
    """Check if MongoDB is online and reachable."""
    try:
        client = get_client()
        if client:
            client.admin.command("ping")
            state.mongo_connected = True
            return True
    except Exception:
        pass
    state.mongo_connected = False
    return False

def load_settings():
    """Load settings from MongoDB into runtime state if available."""
    db = get_db()
    if db is None:
        return {
            "device_name": state.device_name,
            "upload_dir": state.upload_dir,
            "auto_approve": state.auto_approve,
            "encryption_enabled": state.encryption_enabled,
            "encryption_key": state.encryption_key,
            "compression_enabled": state.compression_enabled,
            "compression_level": state.compression_level,
            "mongo_uri": state.mongo_uri,
            "mongo_connected": False
        }

    try:
        doc = db.settings.find_one({"_id": "app_settings"})
        if doc:
            state.device_name = doc.get("device_name", state.device_name)
            state.upload_dir = doc.get("upload_dir", state.upload_dir)
            state.auto_approve = doc.get("auto_approve", state.auto_approve)
            state.encryption_enabled = doc.get("encryption_enabled", state.encryption_enabled)
            state.encryption_key = doc.get("encryption_key", state.encryption_key)
            state.compression_enabled = doc.get("compression_enabled", state.compression_enabled)
            state.compression_level = doc.get("compression_level", state.compression_level)
            state.mongo_connected = True
        else:
            # Initialize default document
            save_settings({
                "device_name": state.device_name,
                "upload_dir": state.upload_dir,
                "auto_approve": state.auto_approve,
                "encryption_enabled": state.encryption_enabled,
                "encryption_key": state.encryption_key,
                "compression_enabled": state.compression_enabled,
                "compression_level": state.compression_level,
            })
    except Exception as e:
        print(f"⚠️ MongoDB load_settings warning: {e}")
        state.mongo_connected = False

    return get_settings_dict()

def save_settings(settings_dict):
    """Save settings to MongoDB and update runtime state."""
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
    if "mongo_uri" in settings_dict and settings_dict["mongo_uri"]:
        state.mongo_uri = str(settings_dict["mongo_uri"])

    db = get_db()
    if db is not None:
        try:
            update_data = {
                "device_name": state.device_name,
                "upload_dir": state.upload_dir,
                "auto_approve": state.auto_approve,
                "encryption_enabled": state.encryption_enabled,
                "encryption_key": state.encryption_key,
                "compression_enabled": state.compression_enabled,
                "compression_level": state.compression_level,
                "updated_at": time.time()
            }
            db.settings.update_one({"_id": "app_settings"}, {"$set": update_data}, upsert=True)
            state.mongo_connected = True
        except Exception as e:
            print(f"⚠️ MongoDB save_settings warning: {e}")
            state.mongo_connected = False

    return get_settings_dict()

def get_settings_dict():
    """Return dictionary of current settings."""
    return {
        "device_name": state.device_name,
        "upload_dir": state.upload_dir,
        "auto_approve": state.auto_approve,
        "encryption_enabled": state.encryption_enabled,
        "encryption_key": state.encryption_key,
        "compression_enabled": state.compression_enabled,
        "compression_level": state.compression_level,
        "mongo_uri": state.mongo_uri,
        "mongo_connected": state.mongo_connected
    }

# -----------------------------------------------------------------------------
# Peer Name / Alias Mapping
# -----------------------------------------------------------------------------
def get_peer_alias(ip):
    """Retrieve custom name for an IP from MongoDB."""
    db = get_db()
    if db is not None:
        try:
            doc = db.peer_aliases.find_one({"ip": ip})
            if doc:
                return doc.get("name")
        except Exception:
            pass
    return None

def set_peer_alias(ip, name, notes=""):
    """Set or update custom alias/name for an IP."""
    clean_ip = str(ip).strip()
    clean_name = str(name).strip()
    
    db = get_db()
    if db is not None:
        try:
            db.peer_aliases.update_one(
                {"ip": clean_ip},
                {"$set": {
                    "ip": clean_ip,
                    "name": clean_name,
                    "notes": notes,
                    "updated_at": time.time()
                }},
                upsert=True
            )
            return True
        except Exception as e:
            print(f"⚠️ MongoDB set_peer_alias error: {e}")
    return False

def delete_peer_alias(ip):
    """Remove custom name alias for an IP."""
    db = get_db()
    if db is not None:
        try:
            res = db.peer_aliases.delete_one({"ip": ip})
            return res.deleted_count > 0
        except Exception:
            pass
    return False

def get_all_peer_aliases():
    """Return dict of all ip -> name aliases."""
    aliases = {}
    db = get_db()
    if db is not None:
        try:
            cursor = db.peer_aliases.find()
            for doc in cursor:
                aliases[doc["ip"]] = {
                    "ip": doc["ip"],
                    "name": doc.get("name", doc["ip"]),
                    "notes": doc.get("notes", ""),
                    "updated_at": doc.get("updated_at", 0)
                }
        except Exception:
            pass
    return aliases

# -----------------------------------------------------------------------------
# Transfer History
# -----------------------------------------------------------------------------
def record_transfer(transfer_data):
    """Record a transfer log into MongoDB."""
    db = get_db()
    if db is not None:
        try:
            record = dict(transfer_data)
            record["timestamp"] = time.time()
            db.transfers.insert_one(record)
        except Exception:
            pass

def get_transfer_history(limit=50):
    """Fetch transfer history from MongoDB."""
    db = get_db()
    if db is not None:
        try:
            cursor = db.transfers.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
            return list(cursor)
        except Exception:
            pass
    return []

def clear_transfer_history():
    """Clear transfer history collection."""
    db = get_db()
    if db is not None:
        try:
            res = db.transfers.delete_many({})
            return res.deleted_count
        except Exception:
            pass
    return 0

# -----------------------------------------------------------------------------
# Clipboard History
# -----------------------------------------------------------------------------
def save_clipboard_item(text, sender="local", sender_ip="127.0.0.1"):
    """Persist clipboard snippet to MongoDB."""
    db = get_db()
    if db is not None:
        try:
            db.clipboard.insert_one({
                "text": text,
                "sender": sender,
                "sender_ip": sender_ip,
                "timestamp": time.time()
            })
        except Exception:
            pass

def get_clipboard_history(limit=50):
    """Fetch clipboard history from MongoDB."""
    db = get_db()
    if db is not None:
        try:
            cursor = db.clipboard.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
            return list(cursor)
        except Exception:
            pass
    return []
