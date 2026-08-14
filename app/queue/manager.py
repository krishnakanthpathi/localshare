"""
Transfer Queue Manager
Manages FIFO and multi-folder batch queuing, concurrency limits, task progress and worker threads.
"""

import os
import time
import threading
from app.config import state
from app.queue.models import TransferTask, BatchTransferTask, TransferStatus, TransferDirection
from app.utils import is_compressible_file

class TransferQueueManager:
    """Manages outbound file transfer batches and worker execution."""

    def __init__(self, max_concurrent_transfers=2):
        self.max_concurrent_transfers = max_concurrent_transfers
        self.batches: dict[str, BatchTransferTask] = {}
        self.lock = threading.Lock()
        self.worker_thread = None
        self.running = True
        self.execution_handler = None  # Hook injected by transfer.client

    def set_execution_handler(self, handler_fn):
        """Set callback function to execute a single TransferTask."""
        self.execution_handler = handler_fn

    def enqueue_paths(
        self,
        target_ip: str,
        paths: list[str],
        target_name: str = "",
        encrypt: bool = None,
        compress: bool = None
    ) -> BatchTransferTask:
        """
        Scan and enqueue multiple files and folder trees into a structured BatchTransferTask.
        """
        use_encryption = state.encryption_enabled if encrypt is None else encrypt
        use_compression = state.compression_enabled if compress is None else compress

        batch = BatchTransferTask(
            target_ip=target_ip,
            root_paths=paths,
            target_name=target_name or target_ip
        )

        for p in paths:
            abs_p = os.path.abspath(p)
            if not os.path.exists(abs_p):
                continue

            if os.path.isfile(abs_p):
                fsize = os.path.getsize(abs_p)
                task = TransferTask(
                    local_path=abs_p,
                    relative_path=os.path.basename(abs_p),
                    filesize=fsize,
                    target_ip=target_ip,
                    direction=TransferDirection.OUTBOUND,
                    encrypted=use_encryption,
                    compressed=use_compression and is_compressible_file(abs_p)
                )
                batch.add_task(task)

            elif os.path.isdir(abs_p):
                # Preserving folder name as root
                folder_name = os.path.basename(os.path.normpath(abs_p))
                for root, _, files in os.walk(abs_p):
                    for file in files:
                        full_f = os.path.join(root, file)
                        rel_from_folder = os.path.relpath(full_f, start=abs_p)
                        rel_path = os.path.join(folder_name, rel_from_folder).replace("\\", "/")
                        fsize = os.path.getsize(full_f)

                        task = TransferTask(
                            local_path=full_f,
                            relative_path=rel_path,
                            filesize=fsize,
                            target_ip=target_ip,
                            direction=TransferDirection.OUTBOUND,
                            encrypted=use_encryption,
                            compressed=use_compression and is_compressible_file(full_f)
                        )
                        batch.add_task(task)

        with self.lock:
            self.batches[batch.id] = batch

        # Trigger worker thread if not running
        self._ensure_worker_running()
        return batch

    def _ensure_worker_running(self):
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()

    def _worker_loop(self):
        """Worker loop executing queued tasks."""
        while self.running:
            task_to_run = None
            with self.lock:
                # Find next queued task across active batches
                for batch in list(self.batches.values()):
                    if batch.status in (TransferStatus.CANCELLED, TransferStatus.PAUSED):
                        continue

                    for t in batch.tasks:
                        if t.status == TransferStatus.QUEUED:
                            t.status = TransferStatus.IN_PROGRESS
                            t.start_time = time.time()
                            task_to_run = t
                            if batch.start_time == 0:
                                batch.start_time = time.time()
                            batch.status = TransferStatus.IN_PROGRESS
                            break
                    if task_to_run:
                        break

            if task_to_run:
                if self.execution_handler:
                    try:
                        self.execution_handler(task_to_run)
                    except Exception as e:
                        task_to_run.status = TransferStatus.FAILED
                        task_to_run.error_message = str(e)
                else:
                    task_to_run.status = TransferStatus.COMPLETED

                with self.lock:
                    task_to_run.end_time = time.time()
                    if task_to_run.batch_id in self.batches:
                        self.batches[task_to_run.batch_id].update_aggregate_metrics()
            else:
                time.sleep(0.5)

    def cancel_batch(self, batch_id: str) -> bool:
        with self.lock:
            if batch_id in self.batches:
                batch = self.batches[batch_id]
                batch.status = TransferStatus.CANCELLED
                for t in batch.tasks:
                    if t.status in (TransferStatus.QUEUED, TransferStatus.IN_PROGRESS):
                        t.status = TransferStatus.CANCELLED
                return True
        return False

    def pause_batch(self, batch_id: str) -> bool:
        with self.lock:
            if batch_id in self.batches:
                self.batches[batch_id].status = TransferStatus.PAUSED
                return True
        return False

    def resume_batch(self, batch_id: str) -> bool:
        with self.lock:
            if batch_id in self.batches:
                self.batches[batch_id].status = TransferStatus.QUEUED
                self._ensure_worker_running()
                return True
        return False

    def get_batch(self, batch_id: str) -> BatchTransferTask | None:
        with self.lock:
            return self.batches.get(batch_id)

    def get_all_batches(self) -> list[dict]:
        with self.lock:
            return [b.to_dict() for b in self.batches.values()]

    def clear_completed(self):
        with self.lock:
            completed_ids = [
                bid for bid, b in self.batches.items()
                if b.status in (TransferStatus.COMPLETED, TransferStatus.CANCELLED, TransferStatus.FAILED)
            ]
            for bid in completed_ids:
                del self.batches[bid]
        return len(completed_ids)

# Singleton queue manager
queue_manager = TransferQueueManager()
