"""
Virtual KVM Mouse Sharing View
Provides UI controls to share and receive cursor movements across LAN & Tailscale nodes.
"""

from __future__ import annotations

import threading
from typing import Optional
import customtkinter as ctk

from app.ui.constants import (
    PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL,
    RADIUS_TAG, RADIUS_CONTROL, RADIUS_CARD,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_DESTRUCTIVE, COLOR_DESTRUCTIVE_HOVER,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_MUTED_TEXT,
    COLOR_CARD_BG, COLOR_BORDER, COLOR_INSET_BG
)
from app.config import INPUT_PORT
from app.input.host import MouseHost
from app.input.client import MouseClient


class MouseView(ctk.CTkFrame):
    """View providing controls for Virtual KVM mouse sharing."""

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app

        self.current_host: Optional[MouseHost] = None
        self.current_client: Optional[MouseClient] = None
        self.worker_thread: Optional[threading.Thread] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Header Toolbar Card
        self.header_card = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.header_card.grid(row=0, column=0, sticky="ew", padx=PAD_LG, pady=(PAD_LG, PAD_SM))
        self.header_card.grid_columnconfigure(0, weight=1)

        title_box = ctk.CTkFrame(self.header_card, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w", padx=PAD_MD, pady=PAD_MD)

        self.lbl_title = ctk.CTkLabel(
            title_box,
            text="Virtual KVM • Seamless Mouse Sharing",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_subtitle = ctk.CTkLabel(
            title_box,
            text="Share single mouse and trackpad across screens over LAN or Tailscale with 6-byte UDP protocol",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_MUTED_TEXT,
            anchor="w"
        )
        self.lbl_subtitle.pack(anchor="w")

        # Live Status Badge
        badge_box = ctk.CTkFrame(self.header_card, fg_color="transparent")
        badge_box.grid(row=0, column=1, sticky="e", padx=PAD_MD, pady=PAD_MD)

        self.lbl_status_badge = ctk.CTkLabel(
            badge_box,
            text="  ⚪ Inactive  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLOR_MUTED_TEXT,
            text_color="#FFFFFF",
            corner_radius=RADIUS_TAG
        )
        self.lbl_status_badge.pack(side="right")

        # 2. Main Scrollable Container with Host & Client Sections
        self.content_scroll = ctk.CTkScrollableFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.content_scroll.grid(row=1, column=0, sticky="nsew", padx=PAD_LG, pady=PAD_SM)
        self.content_scroll.grid_columnconfigure(0, weight=1)

        # --- SECTION A: HOST MODE (Control Remote Machine) ---
        self._build_host_section(self.content_scroll)

        # Divider
        divider = ctk.CTkFrame(self.content_scroll, height=1, fg_color=COLOR_BORDER)
        divider.pack(fill="x", padx=PAD_MD, pady=PAD_LG)

        # --- SECTION B: CLIENT MODE (Receive Cursor Control) ---
        self._build_client_section(self.content_scroll)

    def _build_host_section(self, parent) -> None:
        sec_box = ctk.CTkFrame(parent, fg_color="transparent")
        sec_box.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        sec_box.grid_columnconfigure(1, weight=1)

        lbl_sec = ctk.CTkLabel(
            sec_box,
            text="🎮 Host Mode (Transmit Cursor to Remote Device)",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        lbl_sec.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, PAD_SM))

        lbl_desc = ctk.CTkLabel(
            sec_box,
            text="Move your cursor past your display's edge to seamlessly control the remote laptop/desktop. Press ESC anytime to instantly return.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_MUTED_TEXT,
            justify="left",
            anchor="w"
        )
        lbl_desc.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, PAD_MD))

        # Target Peer Row
        lbl_target = ctk.CTkLabel(sec_box, text="Target Peer:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_target.grid(row=2, column=0, sticky="w", padx=(0, PAD_MD), pady=PAD_XS)

        self.peer_option_menu = ctk.CTkOptionMenu(
            sec_box,
            values=["<Select discovered peer>"],
            height=32,
            corner_radius=RADIUS_CONTROL
        )
        self.peer_option_menu.grid(row=2, column=1, sticky="ew", pady=PAD_XS)

        # Manual Target IP Entry
        lbl_manual = ctk.CTkLabel(sec_box, text="Or Direct IP:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_manual.grid(row=3, column=0, sticky="w", padx=(0, PAD_MD), pady=PAD_XS)

        self.entry_target_ip = ctk.CTkEntry(
            sec_box,
            placeholder_text="e.g. 192.168.1.50 or Tailscale 100.x.x.x",
            height=32,
            corner_radius=RADIUS_CONTROL
        )
        self.entry_target_ip.grid(row=3, column=1, sticky="ew", pady=PAD_XS)

        # Edge Selector Row
        lbl_edge = ctk.CTkLabel(sec_box, text="Switch Edge:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_edge.grid(row=4, column=0, sticky="w", padx=(0, PAD_MD), pady=PAD_XS)

        self.seg_host_edge = ctk.CTkSegmentedButton(
            sec_box,
            values=["Right", "Left"],
            corner_radius=RADIUS_CONTROL
        )
        self.seg_host_edge.set("Right")
        self.seg_host_edge.grid(row=4, column=1, sticky="w", pady=PAD_XS)

        # Action Button
        self.btn_toggle_host = ctk.CTkButton(
            sec_box,
            text="Start Mouse Host",
            height=36,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            command=self._on_toggle_host
        )
        self.btn_toggle_host.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(PAD_MD, 0))

    def _build_client_section(self, parent) -> None:
        sec_box = ctk.CTkFrame(parent, fg_color="transparent")
        sec_box.pack(fill="x", padx=PAD_MD, pady=PAD_SM)
        sec_box.grid_columnconfigure(1, weight=1)

        lbl_sec = ctk.CTkLabel(
            sec_box,
            text="🖥️ Client Mode (Receive Remote Cursor)",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        lbl_sec.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, PAD_SM))

        lbl_desc = ctk.CTkLabel(
            sec_box,
            text=f"Listens for incoming mouse streams on UDP port {INPUT_PORT}. Pushing cursor past the designated return edge releases control back to the Host.",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_MUTED_TEXT,
            justify="left",
            anchor="w"
        )
        lbl_desc.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, PAD_MD))

        # Return Edge Selector
        lbl_return_edge = ctk.CTkLabel(sec_box, text="Return Edge:", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_return_edge.grid(row=2, column=0, sticky="w", padx=(0, PAD_MD), pady=PAD_XS)

        self.seg_client_edge = ctk.CTkSegmentedButton(
            sec_box,
            values=["Left", "Right"],
            corner_radius=RADIUS_CONTROL
        )
        self.seg_client_edge.set("Left")
        self.seg_client_edge.grid(row=2, column=1, sticky="w", pady=PAD_XS)

        # Action Button
        self.btn_toggle_client = ctk.CTkButton(
            sec_box,
            text="Start Mouse Client",
            height=36,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_SUCCESS,
            command=self._on_toggle_client
        )
        self.btn_toggle_client.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(PAD_MD, 0))

    def update_peers_list(self, peers: list[dict]) -> None:
        """Update target peers dropdown when mesh scanner discovers peers."""
        items = []
        for p in peers:
            name = p.get("name", "Unknown")
            ip = p.get("ip", "")
            ptype = p.get("type", "lan").upper()
            items.append(f"{name} ({ip}) [{ptype}]")

        if not items:
            self.peer_option_menu.configure(values=["<No peers discovered>"])
            self.peer_option_menu.set("<No peers discovered>")
        else:
            self.peer_option_menu.configure(values=items)
            current = self.peer_option_menu.get()
            if not current or current == "<No peers discovered>":
                self.peer_option_menu.set(items[0])

    def _resolve_target_ip(self) -> Optional[str]:
        manual = self.entry_target_ip.get().strip()
        if manual:
            return manual

        selected = self.peer_option_menu.get()
        if "(" in selected and ")" in selected:
            return selected.split("(")[1].split(")")[0].strip()
        return None

    def _on_toggle_host(self) -> None:
        if self.current_host and self.current_host.running:
            self.stop_all()
            return

        target_ip = self._resolve_target_ip()
        if not target_ip:
            self.app.event_queue.put(("log", "[KVM] Please select a target peer or enter a target IP."))
            return

        edge = self.seg_host_edge.get().lower()

        try:
            self.current_host = MouseHost(target_ip=target_ip, edge=edge)
            self.worker_thread = threading.Thread(target=self.current_host.start, daemon=True)
            self.worker_thread.start()

            self.btn_toggle_host.configure(
                text="Stop Mouse Host",
                fg_color=COLOR_DESTRUCTIVE,
                hover_color=COLOR_DESTRUCTIVE_HOVER
            )
            self.btn_toggle_client.configure(state="disabled")
            self.lbl_status_badge.configure(text="  🟢 Host Active  ", fg_color=COLOR_ACCENT)
            self.app.event_queue.put(("log", f"[KVM] Started Mouse Host targeting {target_ip} ({edge} edge)."))
        except Exception as e:
            self.app.event_queue.put(("log", f"[KVM] Failed to start Mouse Host: {e}"))

    def _on_toggle_client(self) -> None:
        if self.current_client and self.current_client.running:
            self.stop_all()
            return

        edge = self.seg_client_edge.get().lower()

        try:
            self.current_client = MouseClient(edge=edge)
            self.worker_thread = threading.Thread(target=self.current_client.start, daemon=True)
            self.worker_thread.start()

            self.btn_toggle_client.configure(
                text="Stop Mouse Client",
                fg_color=COLOR_DESTRUCTIVE,
                hover_color=COLOR_DESTRUCTIVE_HOVER
            )
            self.btn_toggle_host.configure(state="disabled")
            self.lbl_status_badge.configure(text="  🟢 Client Active  ", fg_color=COLOR_SUCCESS)
            self.app.event_queue.put(("log", f"[KVM] Started Mouse Client listening on UDP port {INPUT_PORT} ({edge} return edge)."))
        except Exception as e:
            self.app.event_queue.put(("log", f"[KVM] Failed to start Mouse Client: {e}"))

    def stop_all(self) -> None:
        """Clean shutdown of active Host or Client."""
        if self.current_host:
            try:
                self.current_host.stop()
            except Exception:
                pass
            self.current_host = None

        if self.current_client:
            try:
                self.current_client.stop()
            except Exception:
                pass
            self.current_client = None

        self.btn_toggle_host.configure(
            text="Start Mouse Host",
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            state="normal"
        )
        self.btn_toggle_client.configure(
            text="Start Mouse Client",
            fg_color=COLOR_SUCCESS,
            state="normal"
        )
        self.lbl_status_badge.configure(text="  ⚪ Inactive  ", fg_color=COLOR_MUTED_TEXT)
