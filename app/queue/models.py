"""
Queue Models: TransferTask, BatchTransferTask, Statuses and Directions
"""

import time
import uuid
from enum import Enum

class TransferStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class TransferDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"

class TransferTask:
    """Represents a single file transfer unit."""
    def __init__(
        self,
        local_path: str,
        relative_path: str,
        filesize: int,
        target_ip: str,
        sender_ip: str = "127.0.0.1",
        direction: TransferDirection = TransferDirection.OUTBOUND,
        batch_id: str = "",
        task_id: str = None,
        encrypted: bool = False,
        compressed: bool = True
    ):
        self.id = task_id or str(uuid.uuid4())
        self.batch_id = batch_id
        self.direction = direction
        self.target_ip = target_ip
        self.sender_ip = sender_ip
        self.local_path = local_path
        self.relative_path = relative_path
        self.filename = relative_path.replace("\\", "/").split("/")[-1]
        self.filesize = filesize
        self.transferred_bytes = 0
        self.status = TransferStatus.QUEUED
        self.speed = 0.0  # Bytes per second
        self.eta = 0.0    # Seconds
        self.encrypted = encrypted
        self.compressed = compressed
        self.checksum = ""
        self.error_message = ""
        self.created_at = time.time()
        self.start_time = 0.0
        self.end_time = 0.0

    @property
    def progress_percent(self) -> float:
        if self.filesize <= 0:
            return 100.0 if self.status == TransferStatus.COMPLETED else 0.0
        return min(round((self.transferred_bytes / self.filesize) * 100, 1), 100.0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "direction": self.direction.value,
            "target_ip": self.target_ip,
            "sender_ip": self.sender_ip,
            "local_path": self.local_path,
            "relative_path": self.relative_path,
            "filename": self.filename,
            "filesize": self.filesize,
            "transferred_bytes": self.transferred_bytes,
            "progress_percent": self.progress_percent,
            "status": self.status.value,
            "speed": round(self.speed, 2),
            "speed_mb": round(self.speed / (1024 * 1024), 2),
            "eta": round(self.eta, 1),
            "encrypted": self.encrypted,
            "compressed": self.compressed,
            "checksum": self.checksum,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "start_time": self.start_time,
            "end_time": self.end_time
        }

class BatchTransferTask:
    """Represents a batch of multiple folders and files to be transferred."""
    def __init__(
        self,
        target_ip: str,
        root_paths: list[str],
        target_name: str = "",
        batch_id: str = None
    ):
        self.id = batch_id or str(uuid.uuid4())
        self.target_ip = target_ip
        self.target_name = target_name or target_ip
        self.root_paths = root_paths
        self.tasks: list[TransferTask] = []
        self.total_bytes = 0
        self.transferred_bytes = 0
        self.status = TransferStatus.QUEUED
        self.speed = 0.0
        self.eta = 0.0
        self.created_at = time.time()
        self.start_time = 0.0
        self.end_time = 0.0

    def add_task(self, task: TransferTask):
        task.batch_id = self.id
        self.tasks.append(task)
        self.total_bytes += task.filesize

    def update_aggregate_metrics(self):
        """Update aggregate batch transferred bytes and progress."""
        total_transferred = sum(t.transferred_bytes for t in self.tasks)
        self.transferred_bytes = total_transferred
        
        # Aggregate active speeds
        active_speeds = [t.speed for t in self.tasks if t.status == TransferStatus.IN_PROGRESS]
        self.speed = sum(active_speeds)
        
        remaining = max(self.total_bytes - self.transferred_bytes, 0)
        self.eta = (remaining / self.speed) if self.speed > 0 else 0.0

        if all(t.status == TransferStatus.COMPLETED for t in self.tasks) and self.tasks:
            self.status = TransferStatus.COMPLETED
            if self.end_time == 0:
                self.end_time = time.time()
        elif any(t.status == TransferStatus.IN_PROGRESS for t in self.tasks):
            self.status = TransferStatus.IN_PROGRESS
        elif any(t.status == TransferStatus.FAILED for t in self.tasks):
            if all(t.status in (TransferStatus.COMPLETED, TransferStatus.FAILED, TransferStatus.CANCELLED) for t in self.tasks):
                self.status = TransferStatus.FAILED

    @property
    def progress_percent(self) -> float:
        if self.total_bytes <= 0:
            return 100.0 if self.status == TransferStatus.COMPLETED else 0.0
        return min(round((self.transferred_bytes / self.total_bytes) * 100, 1), 100.0)

    def to_dict(self) -> dict:
        self.update_aggregate_metrics()
        return {
            "id": self.id,
            "target_ip": self.target_ip,
            "target_name": self.target_name,
            "root_paths": self.root_paths,
            "total_files": len(self.tasks),
            "completed_files": sum(1 for t in self.tasks if t.status == TransferStatus.COMPLETED),
            "total_bytes": self.total_bytes,
            "transferred_bytes": self.transferred_bytes,
            "progress_percent": self.progress_percent,
            "status": self.status.value,
            "speed": round(self.speed, 2),
            "speed_mb": round(self.speed / (1024 * 1024), 2),
            "eta": round(self.eta, 1),
            "created_at": self.created_at,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "tasks": [t.to_dict() for t in self.tasks]
        }
