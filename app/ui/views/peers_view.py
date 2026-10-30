"""
Discovered Mesh Peers View
Displays real-time LAN & Tailscale peers with latency, OS tags, and direct actions.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog
import customtkinter as ctk

from app.ui.constants import (
    PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL,
    RADIUS_TAG, RADIUS_CONTROL, RADIUS_CARD,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_MUTED_TEXT,
    COLOR_CARD_BG, COLOR_BORDER, COLOR_INSET_BG
)
from app.storage import get_peer_alias, set_peer_alias


class PeersView(ctk.CTkFrame):
    """View displaying active peers discovered across LAN and Tailscale."""

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._current_peers = []
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
            text="Discovered Mesh Peers",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_subtitle = ctk.CTkLabel(
            title_box,
            text="Real-time UDP beacon and Tailscale mesh nodes",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_MUTED_TEXT,
            anchor="w"
        )
        self.lbl_subtitle.pack(anchor="w")

        btn_box = ctk.CTkFrame(self.header_card, fg_color="transparent")
        btn_box.grid(row=0, column=1, sticky="e", padx=PAD_MD, pady=PAD_MD)

        self.btn_refresh = ctk.CTkButton(
            btn_box,
            text="Scan Now",
            width=100,
            height=32,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            command=self.app.trigger_peer_scan
        )
        self.btn_refresh.pack(side="right", padx=(PAD_SM, 0))

        # 2. Scrollable Peer Cards Container
        self.peer_scroll = ctk.CTkScrollableFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.peer_scroll.grid(row=1, column=0, sticky="nsew", padx=PAD_LG, pady=PAD_SM)
        self.peer_scroll.grid_columnconfigure(0, weight=1)

        # 3. Manual IP Connect Card (Footer)
        self.manual_card = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.manual_card.grid(row=2, column=0, sticky="ew", padx=PAD_LG, pady=(PAD_SM, PAD_LG))
        self.manual_card.grid_columnconfigure(1, weight=1)

        lbl_manual = ctk.CTkLabel(
            self.manual_card,
            text="Manual Direct IP:",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        lbl_manual.grid(row=0, column=0, padx=(PAD_MD, PAD_SM), pady=PAD_MD)

        self.entry_manual_ip = ctk.CTkEntry(
            self.manual_card,
            placeholder_text="Enter LAN or Tailscale IP (e.g., 192.168.1.50 or 100.x.x.x)",
            height=32,
            corner_radius=RADIUS_CONTROL
        )
        self.entry_manual_ip.grid(row=0, column=1, sticky="ew", padx=PAD_SM, pady=PAD_MD)

        self.btn_select_manual = ctk.CTkButton(
            self.manual_card,
            text="Send to IP",
            width=110,
            height=32,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            command=self._on_send_to_manual
        )
        self.btn_select_manual.grid(row=0, column=2, padx=(PAD_SM, PAD_MD), pady=PAD_MD)

        # Render initial placeholder
        self.render_peers([])

    def render_peers(self, peers: list[dict]) -> None:
        """Render the list of discovered mesh peers."""
        self._current_peers = peers

        # Clear existing child widgets in peer_scroll
        for widget in self.peer_scroll.winfo_children():
            widget.destroy()

        if not peers:
            empty_frame = ctk.CTkFrame(self.peer_scroll, fg_color="transparent")
            empty_frame.pack(fill="both", expand=True, pady=PAD_XL * 2)

            ctk.CTkLabel(
                empty_frame,
                text="📡",
                font=ctk.CTkFont(size=40)
            ).pack(pady=(0, PAD_SM))

            ctk.CTkLabel(
                empty_frame,
                text="No Active Mesh Peers Detected",
                font=ctk.CTkFont(size=15, weight="bold")
            ).pack(pady=(0, PAD_XS))

            ctk.CTkLabel(
                empty_frame,
                text="Ensure LocalShare is running on other devices on your local Wi-Fi or Tailscale network.\nClick 'Scan Now' to broadcast a discovery ping.",
                font=ctk.CTkFont(size=12),
                text_color=COLOR_MUTED_TEXT,
                justify="center"
            ).pack()
            return

        for i, peer in enumerate(peers):
            card = self._create_peer_card(self.peer_scroll, peer)
            card.pack(fill="x", expand=True, padx=PAD_SM, pady=PAD_SM)

    def _create_peer_card(self, parent, peer: dict) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            corner_radius=RADIUS_CARD,
            fg_color=COLOR_INSET_BG,
            border_width=1,
            border_color=COLOR_BORDER
        )
        card.grid_columnconfigure(1, weight=1)

        # Online dot & icon
        status_dot = ctk.CTkLabel(
            card,
            text="●",
            text_color=COLOR_SUCCESS[1],
            font=ctk.CTkFont(size=16)
        )
        status_dot.grid(row=0, column=0, rowspan=2, padx=(PAD_MD, PAD_SM), pady=PAD_MD)

        # Peer Info
        ip = peer.get("ip", "Unknown")
        name = peer.get("name", ip)
        port = peer.get("port", 4001)
        ptype = peer.get("type", "lan").upper()
        os_name = str(peer.get("os", "Unknown")).capitalize()
        lat = peer.get("latency", 0.0)

        info_box = ctk.CTkFrame(card, fg_color="transparent")
        info_box.grid(row=0, column=1, rowspan=2, sticky="w", padx=0, pady=PAD_MD)

        top_line = ctk.CTkFrame(info_box, fg_color="transparent")
        top_line.pack(anchor="w")

        lbl_name = ctk.CTkLabel(
            top_line,
            text=name,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        lbl_name.pack(side="left")

        # Type Pill
        pill_color = COLOR_ACCENT if ptype == "TAILSCALE" else COLOR_SUCCESS
        lbl_pill = ctk.CTkLabel(
            top_line,
            text=f" {ptype} ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=pill_color,
            corner_radius=RADIUS_TAG,
            text_color="#FFFFFF"
        )
        lbl_pill.pack(side="left", padx=PAD_SM)

        # Details line
        details = f"{ip}:{port} • OS: {os_name} • Latency: {lat:.1f}ms"
        lbl_details = ctk.CTkLabel(
            info_box,
            text=details,
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color=COLOR_MUTED_TEXT,
            anchor="w"
        )
        lbl_details.pack(anchor="w", pady=(PAD_XS, 0))

        # Actions
        act_box = ctk.CTkFrame(card, fg_color="transparent")
        act_box.grid(row=0, column=2, rowspan=2, sticky="e", padx=PAD_MD, pady=PAD_MD)

        btn_send = ctk.CTkButton(
            act_box,
            text="Send Files",
            width=84,
            height=28,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            command=lambda p=peer: self.app.navigate_to_send(p["ip"], p["name"])
        )
        btn_send.pack(side="left", padx=(0, PAD_XS))

        btn_text = ctk.CTkButton(
            act_box,
            text="Send Text",
            width=80,
            height=28,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            command=lambda p=peer: self.app.navigate_to_snippet(p["ip"], p["name"])
        )
        btn_text.pack(side="left", padx=(0, PAD_XS))

        btn_alias = ctk.CTkButton(
            act_box,
            text="Alias",
            width=56,
            height=28,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_MUTED_TEXT,
            command=lambda p=peer: self._on_edit_alias(p)
        )
        btn_alias.pack(side="left")

        return card

    def _on_send_to_manual(self) -> None:
        target_ip = self.entry_manual_ip.get().strip()
        if not target_ip:
            return
        self.app.navigate_to_send(target_ip, target_ip)

    def _on_edit_alias(self, peer: dict) -> None:
        ip = peer.get("ip")
        current_alias = get_peer_alias(ip) or peer.get("name", "")
        new_alias = simpledialog.askstring("Set Peer Alias", f"Enter friendly name for {ip}:", initialvalue=current_alias)
        if new_alias is not None:
            new_alias = new_alias.strip()
            if new_alias:
                set_peer_alias(ip, new_alias)
            self.app.trigger_peer_scan()
