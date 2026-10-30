"""
Unified Activity & Transfer Log View
Displays real-time logs from ~/.localshare/localshare.log with search and level filters.
"""

from __future__ import annotations

import customtkinter as ctk

from app.ui.constants import (
    PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL,
    RADIUS_TAG, RADIUS_CONTROL, RADIUS_CARD,
    COLOR_ACCENT, COLOR_MUTED_TEXT, COLOR_CARD_BG, COLOR_BORDER, COLOR_INSET_BG
)
from app.config import LOG_FILE
from app.storage import get_recent_log_lines


class LogsView(ctk.CTkFrame):
    """Real-time unified log viewer."""

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._raw_lines: list[str] = []
        self._setup_ui()
        self.reload_logs()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Header & Filters Card
        self.header_card = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.header_card.grid(row=0, column=0, sticky="ew", padx=PAD_LG, pady=(PAD_LG, PAD_SM))
        self.header_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.header_card,
            text="Unified Activity Log",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, padx=PAD_MD, pady=PAD_MD, sticky="w")

        # Filter box
        filter_box = ctk.CTkFrame(self.header_card, fg_color="transparent")
        filter_box.grid(row=0, column=1, padx=PAD_MD, pady=PAD_MD, sticky="e")

        self.entry_search = ctk.CTkEntry(
            filter_box,
            placeholder_text="Search logs...",
            width=160,
            height=30,
            corner_radius=RADIUS_CONTROL
        )
        self.entry_search.pack(side="left", padx=(0, PAD_SM))
        self.entry_search.bind("<KeyRelease>", lambda e: self._apply_filters())

        self.level_menu = ctk.CTkOptionMenu(
            filter_box,
            values=["ALL", "INFO", "WARN", "ERROR", "TRANSFER"],
            width=90,
            height=30,
            corner_radius=RADIUS_CONTROL,
            command=lambda v: self._apply_filters()
        )
        self.level_menu.pack(side="left", padx=(0, PAD_SM))
        self.level_menu.set("ALL")

        self.btn_copy = ctk.CTkButton(
            filter_box,
            text="Copy Log",
            width=75,
            height=30,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_ACCENT,
            command=self._on_copy_logs
        )
        self.btn_copy.pack(side="left", padx=(0, PAD_SM))

        self.btn_refresh = ctk.CTkButton(
            filter_box,
            text="Refresh",
            width=70,
            height=30,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            command=self.reload_logs
        )
        self.btn_refresh.pack(side="left")

        # 2. Log Textbox Card
        self.log_card = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.log_card.grid(row=1, column=0, sticky="nsew", padx=PAD_LG, pady=(PAD_SM, PAD_LG))
        self.log_card.grid_columnconfigure(0, weight=1)
        self.log_card.grid_rowconfigure(0, weight=1)

        self.txt_logs = ctk.CTkTextbox(
            self.log_card,
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color=COLOR_INSET_BG,
            corner_radius=RADIUS_CONTROL,
            wrap="none"
        )
        self.txt_logs.grid(row=0, column=0, sticky="nsew", padx=PAD_MD, pady=PAD_MD)

    def reload_logs(self) -> None:
        """Fetch latest log lines from localshare.log."""
        self._raw_lines = get_recent_log_lines(limit=200)
        self._apply_filters()

    def append_log_line(self, line: str) -> None:
        """Dynamically append a newly emitted log event."""
        self._raw_lines.append(line)
        lvl = self.level_menu.get()
        query = self.entry_search.get().strip().lower()

        if lvl != "ALL" and f"[{lvl}]" not in line and f"[{lvl:<5}]" not in line:
            return
        if query and query not in line.lower():
            return

        self.txt_logs.configure(state="normal")
        self.txt_logs.insert("end", f"{line}\n")
        self.txt_logs.see("end")
        self.txt_logs.configure(state="disabled")

    def _apply_filters(self) -> None:
        lvl = self.level_menu.get()
        query = self.entry_search.get().strip().lower()

        filtered = []
        for line in self._raw_lines:
            if lvl != "ALL" and f"[{lvl}]" not in line and f"[{lvl:<5}]" not in line:
                continue
            if query and query not in line.lower():
                continue
            filtered.append(line)

        self.txt_logs.configure(state="normal")
        self.txt_logs.delete("1.0", "end")
        if filtered:
            self.txt_logs.insert("end", "\n".join(filtered) + "\n")
            self.txt_logs.see("end")
        else:
            self.txt_logs.insert("end", "-- No matching log entries --\n")
        self.txt_logs.configure(state="disabled")

    def _on_copy_logs(self) -> None:
        text = self.txt_logs.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.btn_copy.configure(text="Copied!")
        self.after(1500, lambda: self.btn_copy.configure(text="Copy Log"))
