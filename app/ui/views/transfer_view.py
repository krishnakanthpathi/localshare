"""
File & Folder Batch Transfer View
Adheres to Apple HIG for selection, queue orchestration, and live telemetry tracking.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from app.ui.constants import (
    PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL,
    RADIUS_TAG, RADIUS_CONTROL, RADIUS_CARD,
    COLOR_ACCENT, COLOR_DESTRUCTIVE, COLOR_DESTRUCTIVE_HOVER, COLOR_SUCCESS,
    COLOR_WARNING, COLOR_MUTED_TEXT, COLOR_CARD_BG, COLOR_BORDER, COLOR_INSET_BG
)
from app.config import state
from app.utils import format_bytes
from app.queue.manager import queue_manager
from app.queue.models import TransferStatus


class TransferView(ctk.CTkFrame):
    """File & Multi-Folder Batch Transfer Hub."""

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.selected_paths: list[str] = []
        self.current_batch_id: str | None = None
        self._peers_cache: list[dict] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # Queue container absorbs remaining space

        # 1. Source Picker Card
        self.source_card = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.source_card.grid(row=0, column=0, sticky="ew", padx=PAD_LG, pady=(PAD_LG, PAD_SM))
        self.source_card.grid_columnconfigure(1, weight=1)

        btn_pick_row = ctk.CTkFrame(self.source_card, fg_color="transparent")
        btn_pick_row.grid(row=0, column=0, sticky="w", padx=PAD_MD, pady=PAD_MD)

        self.btn_add_files = ctk.CTkButton(
            btn_pick_row,
            text="+ Add Files",
            width=110,
            height=32,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            command=self._on_choose_files
        )
        self.btn_add_files.pack(side="left", padx=(0, PAD_SM))

        self.btn_add_folder = ctk.CTkButton(
            btn_pick_row,
            text="+ Add Folder",
            width=110,
            height=32,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_ACCENT,
            command=self._on_choose_folder
        )
        self.btn_add_folder.pack(side="left", padx=(0, PAD_SM))

        self.btn_clear = ctk.CTkButton(
            btn_pick_row,
            text="Clear",
            width=65,
            height=32,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_MUTED_TEXT,
            command=self._on_clear_selection
        )
        self.btn_clear.pack(side="left")

        self.lbl_selected_summary = ctk.CTkLabel(
            self.source_card,
            text="No files or folders selected",
            font=ctk.CTkFont(size=13),
            text_color=COLOR_MUTED_TEXT,
            anchor="e"
        )
        self.lbl_selected_summary.grid(row=0, column=1, sticky="ew", padx=PAD_MD, pady=PAD_MD)

        # Selected items text container
        self.txt_selected = ctk.CTkTextbox(
            self.source_card,
            height=70,
            font=ctk.CTkFont(family="Courier New", size=11),
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_INSET_BG
        )
        self.txt_selected.grid(row=1, column=0, columnspan=2, sticky="ew", padx=PAD_MD, pady=(0, PAD_MD))
        self.txt_selected.configure(state="disabled")

        # 2. Target Peer & Options Card
        self.target_card = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.target_card.grid(row=1, column=0, sticky="ew", padx=PAD_LG, pady=PAD_SM)
        self.target_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.target_card,
            text="Target Peer:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, padx=(PAD_MD, PAD_SM), pady=PAD_MD, sticky="w")

        self.peer_option_menu = ctk.CTkOptionMenu(
            self.target_card,
            values=["<No peers discovered>"],
            corner_radius=RADIUS_CONTROL,
            height=32,
            dynamic_resizing=False
        )
        self.peer_option_menu.grid(row=0, column=1, sticky="ew", padx=PAD_SM, pady=PAD_MD)

        # Action Buttons Row
        action_box = ctk.CTkFrame(self.target_card, fg_color="transparent")
        action_box.grid(row=0, column=2, padx=PAD_MD, pady=PAD_MD, sticky="e")

        self.btn_start = ctk.CTkButton(
            action_box,
            text="Start Transfer",
            width=130,
            height=34,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            command=self._on_start_transfer
        )
        self.btn_start.pack(side="left", padx=(0, PAD_SM))

        self.btn_cancel = ctk.CTkButton(
            action_box,
            text="Cancel",
            width=80,
            height=34,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_DESTRUCTIVE,
            hover_color=COLOR_DESTRUCTIVE_HOVER,
            state="disabled",
            command=self._on_cancel_transfer
        )
        self.btn_cancel.pack(side="left")

        # 3. Telemetry & Progress Card
        self.telemetry_card = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.telemetry_card.grid(row=2, column=0, sticky="ew", padx=PAD_LG, pady=PAD_SM)
        self.telemetry_card.grid_columnconfigure(0, weight=1)

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.telemetry_card, mode="determinate", height=10)
        self.progress_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=PAD_MD, pady=(PAD_MD, PAD_XS))
        self.progress_bar.set(0.0)

        # Metrics text row
        self.lbl_progress_metrics = ctk.CTkLabel(
            self.telemetry_card,
            text="Ready • 0%",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        self.lbl_progress_metrics.grid(row=1, column=0, sticky="w", padx=PAD_MD, pady=(0, PAD_MD))

        self.lbl_speed_eta = ctk.CTkLabel(
            self.telemetry_card,
            text="Speed: 0.00 MB/s • ETA: --",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_MUTED_TEXT,
            anchor="e"
        )
        self.lbl_speed_eta.grid(row=1, column=1, sticky="e", padx=PAD_MD, pady=(0, PAD_MD))

        # 4. Batches & Queue History Card
        self.queue_card = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.queue_card.grid(row=3, column=0, sticky="nsew", padx=PAD_LG, pady=(PAD_SM, PAD_LG))
        self.queue_card.grid_columnconfigure(0, weight=1)
        self.queue_card.grid_rowconfigure(1, weight=1)

        queue_hdr = ctk.CTkFrame(self.queue_card, fg_color="transparent")
        queue_hdr.grid(row=0, column=0, sticky="ew", padx=PAD_MD, pady=(PAD_MD, PAD_SM))
        queue_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            queue_hdr,
            text="Transfer Batches & Tasks",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        ).grid(row=0, column=0, sticky="w")

        self.btn_clear_queue = ctk.CTkButton(
            queue_hdr,
            text="Clear Finished",
            width=100,
            height=26,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_MUTED_TEXT,
            command=self._on_clear_completed_queue
        )
        self.btn_clear_queue.grid(row=0, column=1, sticky="e")

        self.queue_scroll = ctk.CTkScrollableFrame(self.queue_card, fg_color=COLOR_INSET_BG, corner_radius=RADIUS_CONTROL)
        self.queue_scroll.grid(row=1, column=0, sticky="nsew", padx=PAD_MD, pady=(0, PAD_MD))
        self.queue_scroll.grid_columnconfigure(0, weight=1)

        self.refresh_queue_display()

    def update_peers_menu(self, peers: list[dict]) -> None:
        """Update destination peer dropdown options."""
        self._peers_cache = peers
        options = []
        for p in peers:
            tag = f"{p['name']} ({p['ip']}) [{p.get('type', 'lan').upper()}]"
            options.append(tag)

        if not options:
            options = ["<No peers discovered>"]

        self.peer_option_menu.configure(values=options)
        cur = self.peer_option_menu.get()
        if cur not in options:
            self.peer_option_menu.set(options[0])

    def set_target_peer(self, target_ip: str, target_name: str) -> None:
        """Preselect a specific peer when navigated from PeersView."""
        for opt in self.peer_option_menu._values:
            if target_ip in opt:
                self.peer_option_menu.set(opt)
                return
        custom_opt = f"{target_name} ({target_ip})"
        vals = list(self.peer_option_menu._values)
        if "<No peers discovered>" in vals:
            vals.remove("<No peers discovered>")
        if custom_opt not in vals:
            vals.insert(0, custom_opt)
        self.peer_option_menu.configure(values=vals)
        self.peer_option_menu.set(custom_opt)

    def _on_choose_files(self) -> None:
        files = filedialog.askopenfilenames(title="Select Files to Send")
        if files:
            for f in files:
                if f not in self.selected_paths:
                    self.selected_paths.append(f)
            self._update_selected_display()

    def _on_choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select Folder to Send")
        if folder and folder not in self.selected_paths:
            self.selected_paths.append(folder)
            self._update_selected_display()

    def _on_clear_selection(self) -> None:
        self.selected_paths.clear()
        self._update_selected_display()

    def _update_selected_display(self) -> None:
        total_files = 0
        total_bytes = 0

        self.txt_selected.configure(state="normal")
        self.txt_selected.delete("1.0", "end")

        for p in self.selected_paths:
            if os.path.isfile(p):
                total_files += 1
                sz = os.path.getsize(p)
                total_bytes += sz
                self.txt_selected.insert("end", f"📄 {os.path.basename(p)} ({format_bytes(sz)})\n")
            elif os.path.isdir(p):
                dir_files = 0
                dir_bytes = 0
                for root, _, fnames in os.walk(p):
                    for fn in fnames:
                        dir_files += 1
                        dir_bytes += os.path.getsize(os.path.join(root, fn))
                total_files += dir_files
                total_bytes += dir_bytes
                self.txt_selected.insert("end", f"📁 {os.path.basename(p)}/ ({dir_files} files, {format_bytes(dir_bytes)})\n")

        self.txt_selected.configure(state="disabled")

        if not self.selected_paths:
            self.lbl_selected_summary.configure(text="No files or folders selected", text_color=COLOR_MUTED_TEXT)
        else:
            self.lbl_selected_summary.configure(
                text=f"{len(self.selected_paths)} item(s) selected: {total_files} files ({format_bytes(total_bytes)})",
                text_color=COLOR_ACCENT[1]
            )

    def _resolve_target_ip_and_name(self) -> tuple[str | None, str | None]:
        selected = self.peer_option_menu.get()
        if not selected or selected == "<No peers discovered>":
            return None, None
        
        # Extract IP from string format "Name (IP) [TYPE]"
        if "(" in selected and ")" in selected:
            ip = selected.split("(")[1].split(")")[0].strip()
            name = selected.split("(")[0].strip()
            return ip, name
        return selected.strip(), selected.strip()

    def _on_start_transfer(self) -> None:
        if not self.selected_paths:
            messagebox.showwarning("No Items Selected", "Please select at least one file or folder to send.")
            return

        target_ip, target_name = self._resolve_target_ip_and_name()
        if not target_ip:
            messagebox.showwarning("Target Required", "Please select or specify a target peer.")
            return

        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.btn_add_files.configure(state="disabled")
        self.btn_add_folder.configure(state="disabled")
        self.btn_clear.configure(state="disabled")

        self.lbl_progress_metrics.configure(text=f"Preparing batch to {target_name}...")

        # Enqueue in TransferQueueManager
        batch = queue_manager.enqueue_paths(
            target_ip=target_ip,
            paths=list(self.selected_paths),
            target_name=target_name,
            encrypt=state.encryption_enabled,
            compress=state.compression_enabled
        )
        self.current_batch_id = batch.id
        self.app.event_queue.put(("log", f"[Queue] Enqueued batch {batch.id[:8]} ({len(batch.tasks)} files, {format_bytes(batch.total_bytes)}) to {target_name}"))
        self.refresh_queue_display()

    def _on_cancel_transfer(self) -> None:
        if self.current_batch_id:
            queue_manager.cancel_batch(self.current_batch_id)
            self.app.event_queue.put(("log", f"[Queue] Cancelled batch {self.current_batch_id[:8]}"))
            self.reset_transfer_controls()
            self.refresh_queue_display()

    def reset_transfer_controls(self) -> None:
        self.btn_start.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self.btn_add_files.configure(state="normal")
        self.btn_add_folder.configure(state="normal")
        self.btn_clear.configure(state="normal")
        self.current_batch_id = None

    def update_live_metrics(self) -> None:
        """Polled periodically by main app loop to update transfer stats."""
        if not self.current_batch_id:
            return

        batch = queue_manager.get_batch(self.current_batch_id)
        if not batch:
            return

        batch.update_aggregate_metrics()
        pct = batch.progress_percent
        self.progress_bar.set(pct / 100.0)

        speed_mb = batch.speed / (1024 * 1024)
        speed_mbps = (batch.speed * 8) / (1024 * 1024)
        eta_str = f"{batch.eta:.1f}s" if batch.eta > 0 else "--"

        active_task = next((t for t in batch.tasks if t.status == TransferStatus.IN_PROGRESS), None)
        task_str = f"[{active_task.filename[:20]} {active_task.progress_percent:.0f}%]" if active_task else f"[{batch.status.value}]"

        self.lbl_progress_metrics.configure(text=f"{batch.status.value} • {pct:5.1f}% • {task_str}")
        self.lbl_speed_eta.configure(text=f"Speed: {speed_mb:.2f} MB/s ({speed_mbps:.1f} Mbps) • ETA: {eta_str}")

        if batch.status in (TransferStatus.COMPLETED, TransferStatus.FAILED, TransferStatus.CANCELLED):
            self.reset_transfer_controls()
            self.refresh_queue_display()
            if batch.status == TransferStatus.COMPLETED:
                self.progress_bar.set(1.0)
                self.lbl_progress_metrics.configure(text="Completed Successfully! 100%", text_color=COLOR_SUCCESS[1])

    def refresh_queue_display(self) -> None:
        """Render all active and historical transfer batches."""
        for w in self.queue_scroll.winfo_children():
            w.destroy()

        batches = queue_manager.get_all_batches()
        if not batches:
            ctk.CTkLabel(
                self.queue_scroll,
                text="No transfer batches in queue.",
                font=ctk.CTkFont(size=12),
                text_color=COLOR_MUTED_TEXT
            ).pack(pady=PAD_MD)
            return

        for b in reversed(batches):
            self._render_batch_row(self.queue_scroll, b)

    def _render_batch_row(self, parent, b: dict) -> None:
        row = ctk.CTkFrame(parent, fg_color=COLOR_CARD_BG, corner_radius=RADIUS_CONTROL)
        row.pack(fill="x", expand=True, padx=PAD_XS, pady=PAD_XS)
        row.grid_columnconfigure(1, weight=1)

        status = b.get("status", "QUEUED")
        status_color = COLOR_SUCCESS if status == "COMPLETED" else COLOR_ACCENT if status == "IN_PROGRESS" else COLOR_DESTRUCTIVE if status in ("FAILED", "CANCELLED") else COLOR_MUTED_TEXT

        lbl_st = ctk.CTkLabel(
            row,
            text=f" {status} ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=status_color,
            text_color="#FFFFFF",
            corner_radius=RADIUS_TAG
        )
        lbl_st.grid(row=0, column=0, padx=PAD_SM, pady=PAD_SM)

        info_text = f"Batch {b['id'][:8]} -> {b['target_name']} ({format_bytes(b['total_bytes'])}, {b['completed_files']}/{b['total_files']} files) [{b['progress_percent']}%]"
        ctk.CTkLabel(
            row,
            text=info_text,
            font=ctk.CTkFont(family="Courier New", size=11),
            anchor="w"
        ).grid(row=0, column=1, sticky="w", padx=PAD_SM, pady=PAD_SM)

    def _on_clear_completed_queue(self) -> None:
        queue_manager.clear_completed()
        self.refresh_queue_display()
