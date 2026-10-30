"""
Quick Snippet & Clipboard Synchronization View
Adheres to Apple HIG for instant messaging, clipboard sharing, and receipt history.
"""

from __future__ import annotations

import time
import tkinter as tk
import customtkinter as ctk

from app.ui.constants import (
    PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL,
    RADIUS_TAG, RADIUS_CONTROL, RADIUS_CARD,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_MUTED_TEXT,
    COLOR_CARD_BG, COLOR_BORDER, COLOR_INSET_BG
)
from app.config import state
from app.sync.clipboard import get_system_clipboard, broadcast_text
from app.transfer.client import send_text_snippet


class ClipboardView(ctk.CTkFrame):
    """Text Snippet & Clipboard synchronization interface."""

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._received_snippets: list[dict] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # History absorbs extra height

        # 1. Compose Snippet Card
        self.compose_card = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.compose_card.grid(row=0, column=0, sticky="ew", padx=PAD_LG, pady=(PAD_LG, PAD_SM))
        self.compose_card.grid_columnconfigure(1, weight=1)

        # Header of compose
        comp_hdr = ctk.CTkFrame(self.compose_card, fg_color="transparent")
        comp_hdr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=PAD_MD, pady=(PAD_MD, PAD_SM))
        comp_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            comp_hdr,
            text="Send Text or Sync Clipboard",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        self.btn_load_clip = ctk.CTkButton(
            comp_hdr,
            text="📋 Paste System Clipboard",
            width=170,
            height=28,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_ACCENT,
            command=self._on_paste_system_clipboard
        )
        self.btn_load_clip.grid(row=0, column=1, sticky="e")

        # Text input area
        self.txt_message = ctk.CTkTextbox(
            self.compose_card,
            height=90,
            font=ctk.CTkFont(size=13),
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_INSET_BG
        )
        self.txt_message.grid(row=1, column=0, columnspan=2, sticky="ew", padx=PAD_MD, pady=PAD_XS)

        # Target & Actions Bar
        actions_bar = ctk.CTkFrame(self.compose_card, fg_color="transparent")
        actions_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=PAD_MD, pady=PAD_MD)
        actions_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            actions_bar,
            text="Target:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, padx=(0, PAD_SM), sticky="w")

        self.target_menu = ctk.CTkOptionMenu(
            actions_bar,
            values=["Broadcast to All Peers", "<No peers discovered>"],
            corner_radius=RADIUS_CONTROL,
            height=32,
            dynamic_resizing=False
        )
        self.target_menu.grid(row=0, column=1, sticky="ew", padx=(0, PAD_MD))
        self.target_menu.set("Broadcast to All Peers")

        self.btn_send = ctk.CTkButton(
            actions_bar,
            text="Send Snippet",
            width=120,
            height=32,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            command=self._on_send_snippet
        )
        self.btn_send.grid(row=0, column=2, padx=(0, PAD_SM), sticky="e")

        self.btn_clear = ctk.CTkButton(
            actions_bar,
            text="Clear",
            width=65,
            height=32,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_MUTED_TEXT,
            command=self._on_clear_text
        )
        self.btn_clear.grid(row=0, column=3, sticky="e")

        # 2. Received Snippets History Card
        self.history_card = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.history_card.grid(row=1, column=0, sticky="nsew", padx=PAD_LG, pady=(PAD_SM, PAD_LG))
        self.history_card.grid_columnconfigure(0, weight=1)
        self.history_card.grid_rowconfigure(1, weight=1)

        hist_hdr = ctk.CTkFrame(self.history_card, fg_color="transparent")
        hist_hdr.grid(row=0, column=0, sticky="ew", padx=PAD_MD, pady=(PAD_MD, PAD_SM))
        hist_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hist_hdr,
            text="Received Snippets & Messages",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        self.btn_clear_history = ctk.CTkButton(
            hist_hdr,
            text="Clear All",
            width=80,
            height=26,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_MUTED_TEXT,
            command=self._on_clear_history
        )
        self.btn_clear_history.grid(row=0, column=1, sticky="e")

        self.history_scroll = ctk.CTkScrollableFrame(
            self.history_card,
            fg_color=COLOR_INSET_BG,
            corner_radius=RADIUS_CONTROL
        )
        self.history_scroll.grid(row=1, column=0, sticky="nsew", padx=PAD_MD, pady=(0, PAD_MD))
        self.history_scroll.grid_columnconfigure(0, weight=1)

        self._render_empty_history()

    def update_peers_menu(self, peers: list[dict]) -> None:
        options = ["Broadcast to All Peers"]
        for p in peers:
            options.append(f"{p['name']} ({p['ip']})")

        self.target_menu.configure(values=options)
        cur = self.target_menu.get()
        if cur not in options:
            self.target_menu.set("Broadcast to All Peers")

    def set_target_peer(self, target_ip: str, target_name: str) -> None:
        custom_opt = f"{target_name} ({target_ip})"
        vals = list(self.target_menu._values)
        if custom_opt not in vals:
            vals.append(custom_opt)
            self.target_menu.configure(values=vals)
        self.target_menu.set(custom_opt)

    def _on_paste_system_clipboard(self) -> None:
        clip_text = get_system_clipboard()
        if clip_text:
            self.txt_message.delete("1.0", "end")
            self.txt_message.insert("end", clip_text)
            self.btn_load_clip.configure(text="✅ Pasted!")
            self.after(1500, lambda: self.btn_load_clip.configure(text="📋 Paste System Clipboard"))

    def _on_clear_text(self) -> None:
        self.txt_message.delete("1.0", "end")

    def _on_send_snippet(self) -> None:
        text = self.txt_message.get("1.0", "end-1c").strip()
        if not text:
            return

        target = self.target_menu.get()
        use_encrypt = state.encryption_enabled

        if target == "Broadcast to All Peers":
            peers = self.app.udp_server.get_active_peers() if self.app.udp_server else []
            count = broadcast_text(text, peers, encrypt=use_encrypt)
            self.app.event_queue.put(("log", f"[Snippet] Broadcasted message to {count} active peer(s)."))
            self.btn_send.configure(text="Sent!")
            self.after(1500, lambda: self.btn_send.configure(text="Send Snippet"))
        else:
            target_ip = target
            if "(" in target and ")" in target:
                target_ip = target.split("(")[1].split(")")[0].strip()

            def _worker():
                ok, msg = send_text_snippet(target_ip, text, encrypt=use_encrypt)
                log_msg = f"[Snippet] Sent to {target_ip}: {msg}" if ok else f"[Snippet Error] Failed to {target_ip}: {msg}"
                self.app.event_queue.put(("log", log_msg))

            import threading
            threading.Thread(target=_worker, daemon=True).start()

            self.btn_send.configure(text="Sent!")
            self.after(1500, lambda: self.btn_send.configure(text="Send Snippet"))

    def add_received_snippet(self, sender: str, text: str, is_encrypted: bool = False) -> None:
        """Called when an incoming snippet is received by TCP server."""
        item = {
            "sender": sender,
            "text": text,
            "is_encrypted": is_encrypted,
            "timestamp": time.strftime("%H:%M:%S")
        }
        self._received_snippets.append(item)
        self._render_snippet_card(item)

    def _render_empty_history(self) -> None:
        for w in self.history_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.history_scroll,
            text="No text snippets received yet.\nIncoming snippets from mesh peers will appear here.",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_MUTED_TEXT,
            justify="center"
        ).pack(pady=PAD_XL)

    def _render_snippet_card(self, item: dict) -> None:
        # If this is first item, clear empty placeholder
        if len(self._received_snippets) == 1:
            for w in self.history_scroll.winfo_children():
                w.destroy()

        card = ctk.CTkFrame(self.history_scroll, corner_radius=RADIUS_CONTROL, fg_color=COLOR_CARD_BG)
        card.pack(fill="x", expand=True, padx=PAD_XS, pady=PAD_XS)
        card.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew", padx=PAD_SM, pady=(PAD_SM, PAD_XS))
        hdr.grid_columnconfigure(0, weight=1)

        enc_badge = "🔒 Encrypted • " if item["is_encrypted"] else ""
        ctk.CTkLabel(
            hdr,
            text=f"{item['sender']} • {enc_badge}{item['timestamp']}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_MUTED_TEXT
        ).grid(row=0, column=0, sticky="w")

        btn_copy = ctk.CTkButton(
            hdr,
            text="Copy",
            width=60,
            height=22,
            corner_radius=RADIUS_TAG,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_ACCENT,
            command=lambda t=item["text"], b=None: self._on_copy_item(t, btn_copy)
        )
        btn_copy.grid(row=0, column=1, sticky="e")

        # Snippet content
        txt = ctk.CTkLabel(
            card,
            text=item["text"],
            font=ctk.CTkFont(size=12),
            justify="left",
            anchor="w",
            wraplength=600
        )
        txt.grid(row=1, column=0, columnspan=2, sticky="w", padx=PAD_SM, pady=(0, PAD_SM))

    def _on_copy_item(self, text: str, btn: ctk.CTkButton) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        btn.configure(text="Copied!")
        self.after(1500, lambda: btn.configure(text="Copy"))

    def _on_clear_history(self) -> None:
        self._received_snippets.clear()
        self._render_empty_history()
