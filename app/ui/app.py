"""
Master LocalShare macOS Desktop Application Window
Adheres strictly to Apple Human Interface Guidelines (HIG) and macos-python-ui patterns:
- Dynamic dark/light appearance matching macOS system settings
- Non-blocking worker threads with thread-safe queue & 40ms drain loop
- Apple-style sidebar navigation and elevated card layouts
- Live transfer telemetry, mesh discovery, and graceful shutdown
"""

from __future__ import annotations

import os
import sys
import time
import queue
import threading
from pathlib import Path
from tkinter import messagebox
import customtkinter as ctk

from app.ui.constants import (
    PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL,
    RADIUS_TAG, RADIUS_CONTROL, RADIUS_CARD,
    COLOR_ACCENT, COLOR_ACCENT_HOVER, COLOR_SUCCESS, COLOR_WARNING,
    COLOR_MUTED_TEXT, COLOR_CANVAS_BG, COLOR_CARD_BG, COLOR_SIDEBAR_BG,
    COLOR_SIDEBAR_ACTIVE, COLOR_BORDER, COLOR_INSET_BG,
    UI_POLL_MS, PEER_REFRESH_MS, METRICS_REFRESH_MS
)
from app.config import state, TCP_PORT, LOG_FILE, CONFIG_FILE
from app.storage import load_settings, save_settings
from app.utils import get_network_interfaces
from app.discovery.udp_beacon import UDPDiscoveryServer, discover_peers
from app.discovery.tailscale import get_tailscale_status
from app.transfer.server import start_tcp_server, stop_tcp_server
from app.queue.manager import queue_manager

from app.ui.views.peers_view import PeersView
from app.ui.views.transfer_view import TransferView
from app.ui.views.clipboard_view import ClipboardView
from app.ui.views.settings_view import SettingsView
from app.ui.views.logs_view import LogsView


class LocalShareMacOSApp(ctk.CTk):
    """Native macOS desktop interface for LocalShare."""

    def __init__(self) -> None:
        super().__init__()

        # 1. Configure macOS Window
        self.title("LocalShare")
        self.geometry("1000x720")
        self.minsize(820, 600)
        self.configure(fg_color=COLOR_CANVAS_BG)

        # 2. State & Concurrency Plumbing
        self.closing = False
        self.event_queue: queue.Queue[tuple[str, any]] = queue.Queue()
        self.active_tab = "peers"
        self._last_peers: list[dict] = []

        # Connect core event listener for non-blocking UI notifications
        state.event_listener = lambda etype, payload: self.event_queue.put((etype, payload))

        # 3. Load Persistent Settings
        load_settings()

        # 4. Start Core Mesh Services in Background
        self._start_core_services()

        # 5. Build Apple HIG Layout
        self._setup_layout()

        # 6. Window protocols & Event Polling Loops
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(UI_POLL_MS, self.drain_ui_events)
        self.after(PEER_REFRESH_MS, self._periodic_peer_refresh)
        self.after(METRICS_REFRESH_MS, self._periodic_metrics_refresh)

    def _start_core_services(self) -> None:
        """Start TCP transfer server and UDP discovery beacon in background threads."""
        try:
            self.tcp_server = start_tcp_server()
        except Exception as e:
            self.tcp_server = None
            print(f"⚠️ TCP server launch error: {e}")

        try:
            self.udp_server = UDPDiscoveryServer()
            self.udp_server.start()
        except Exception as e:
            self.udp_server = None
            print(f"⚠️ UDP beacon launch error: {e}")

    def _setup_layout(self) -> None:
        """Construct the two-column macOS Split-View layout."""
        self.grid_columnconfigure(0, weight=0)  # Sidebar fixed width
        self.grid_columnconfigure(1, weight=1)  # Main content flexible
        self.grid_rowconfigure(0, weight=1)

        # =====================================================================
        # LEFT COLUMN: Apple-Native Sidebar
        # =====================================================================
        self.sidebar = ctk.CTkFrame(
            self,
            width=230,
            corner_radius=0,
            fg_color=COLOR_SIDEBAR_BG
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(7, weight=1)  # Pushes footer card to bottom

        # App Branding Header
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.grid(row=0, column=0, sticky="ew", padx=PAD_LG, pady=(PAD_XL, PAD_MD))

        lbl_logo = ctk.CTkLabel(
            brand_frame,
            text="🚀 LocalShare",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w"
        )
        lbl_logo.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            brand_frame,
            text="Mesh Transfer Engine",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_MUTED_TEXT,
            anchor="w"
        )
        lbl_sub.pack(anchor="w")

        # Divider
        divider = ctk.CTkFrame(self.sidebar, height=1, fg_color=COLOR_BORDER)
        divider.grid(row=1, column=0, sticky="ew", padx=PAD_MD, pady=(0, PAD_MD))

        # Navigation Buttons
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        nav_items = [
            ("peers", "📡  Mesh Peers"),
            ("transfer", "📁  Send & Queue"),
            ("clipboard", "📋  Quick Snippet"),
            ("settings", "⚙️  Settings"),
            ("logs", "📝  Activity Log"),
        ]

        for idx, (key, label) in enumerate(nav_items, start=2):
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                height=36,
                corner_radius=RADIUS_CONTROL,
                font=ctk.CTkFont(size=13, weight="normal"),
                fg_color="transparent",
                text_color=COLOR_MUTED_TEXT,
                hover_color=COLOR_SIDEBAR_ACTIVE,
                command=lambda k=key: self.navigate_to_tab(k)
            )
            btn.grid(row=idx, column=0, sticky="ew", padx=PAD_MD, pady=PAD_XS)
            self.nav_buttons[key] = btn

        # Spacer row 7 absorbs height

        # Bottom Node Info Card in Sidebar
        self.node_card = ctk.CTkFrame(self.sidebar, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.node_card.grid(row=8, column=0, sticky="ew", padx=PAD_MD, pady=PAD_LG)

        net_info = get_network_interfaces()
        prim_ip = net_info.get("primary", "127.0.0.1")
        port = getattr(self.tcp_server, "port", TCP_PORT) if self.tcp_server else TCP_PORT

        self.lbl_node_info = ctk.CTkLabel(
            self.node_card,
            text=f"LAN IP: {prim_ip}\nPort: {port}",
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=COLOR_MUTED_TEXT,
            justify="left",
            anchor="w"
        )
        self.lbl_node_info.pack(fill="x", padx=PAD_SM, pady=PAD_SM)

        # =====================================================================
        # RIGHT COLUMN: Header Status Bar + Content Views
        # =====================================================================
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        # Top Status Pill Bar
        self.header_bar = ctk.CTkFrame(self.main_container, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        self.header_bar.grid(row=0, column=0, sticky="ew", padx=PAD_LG, pady=(PAD_LG, 0))
        self.header_bar.grid_columnconfigure(1, weight=1)

        # Device identity tag
        self.lbl_device_tag = ctk.CTkLabel(
            self.header_bar,
            text=f"💻 {state.device_name}",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.lbl_device_tag.grid(row=0, column=0, padx=PAD_MD, pady=PAD_SM, sticky="w")

        # Status pills container
        self.pills_box = ctk.CTkFrame(self.header_bar, fg_color="transparent")
        self.pills_box.grid(row=0, column=1, sticky="e", padx=PAD_MD, pady=PAD_SM)

        self.lbl_enc_pill = ctk.CTkLabel(
            self.pills_box,
            text=" AES-256 ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLOR_SUCCESS if state.encryption_enabled else COLOR_MUTED_TEXT,
            text_color="#FFFFFF",
            corner_radius=RADIUS_TAG
        )
        self.lbl_enc_pill.pack(side="right", padx=(PAD_XS, 0))

        self.lbl_comp_pill = ctk.CTkLabel(
            self.pills_box,
            text=f" Gzip L{state.compression_level} ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLOR_ACCENT if state.compression_enabled else COLOR_MUTED_TEXT,
            text_color="#FFFFFF",
            corner_radius=RADIUS_TAG
        )
        self.lbl_comp_pill.pack(side="right", padx=(PAD_XS, 0))

        ts = get_tailscale_status()
        self.lbl_ts_pill = ctk.CTkLabel(
            self.pills_box,
            text=" Tailscale " if ts.get("active") else " TS Inactive ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=COLOR_SUCCESS if ts.get("active") else COLOR_MUTED_TEXT,
            text_color="#FFFFFF",
            corner_radius=RADIUS_TAG
        )
        self.lbl_ts_pill.pack(side="right", padx=(PAD_XS, 0))

        # View Host Container
        self.views_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.views_frame.grid(row=1, column=0, sticky="nsew", pady=(PAD_XS, 0))
        self.views_frame.grid_columnconfigure(0, weight=1)
        self.views_frame.grid_rowconfigure(0, weight=1)

        # Instantiate all 5 child views
        self.views: dict[str, ctk.CTkFrame] = {
            "peers": PeersView(self.views_frame, self),
            "transfer": TransferView(self.views_frame, self),
            "clipboard": ClipboardView(self.views_frame, self),
            "settings": SettingsView(self.views_frame, self),
            "logs": LogsView(self.views_frame, self),
        }

        # Initial Navigation to Peers view
        self.navigate_to_tab("peers")

    # =========================================================================
    # Navigation & View Switching
    # =========================================================================

    def navigate_to_tab(self, tab_key: str) -> None:
        """Switch active view with Apple sidebar highlighting."""
        if tab_key not in self.views:
            return

        self.active_tab = tab_key

        # Update sidebar button states
        for key, btn in self.nav_buttons.items():
            if key == tab_key:
                btn.configure(
                    fg_color=COLOR_SIDEBAR_ACTIVE,
                    text_color=COLOR_ACCENT[1],
                    font=ctk.CTkFont(size=13, weight="bold")
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLOR_MUTED_TEXT,
                    font=ctk.CTkFont(size=13, weight="normal")
                )

        # Show only selected view, hide all other views cleanly
        for key, view in self.views.items():
            if key == tab_key:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_forget()

    def navigate_to_send(self, target_ip: str, target_name: str) -> None:
        """Direct shortcut from PeersView to TransferView with target selected."""
        self.navigate_to_tab("transfer")
        self.views["transfer"].set_target_peer(target_ip, target_name)

    def navigate_to_snippet(self, target_ip: str, target_name: str) -> None:
        """Direct shortcut from PeersView to ClipboardView with target selected."""
        self.navigate_to_tab("clipboard")
        self.views["clipboard"].set_target_peer(target_ip, target_name)

    def trigger_peer_scan(self) -> None:
        """Run discovery scan in background worker and dispatch update."""
        def _worker():
            peers = discover_peers(timeout=1.5)
            self.event_queue.put(("peer_scan_done", peers))

        threading.Thread(target=_worker, daemon=True).start()

    def on_settings_updated(self) -> None:
        """Refresh header pills and views when preferences change."""
        self.lbl_device_tag.configure(text=f"💻 {state.device_name}")
        self.lbl_enc_pill.configure(
            fg_color=COLOR_SUCCESS if state.encryption_enabled else COLOR_MUTED_TEXT
        )
        self.lbl_comp_pill.configure(
            text=f" Gzip L{state.compression_level} ",
            fg_color=COLOR_ACCENT if state.compression_enabled else COLOR_MUTED_TEXT
        )
        ts = get_tailscale_status()
        self.lbl_ts_pill.configure(
            text=" Tailscale " if ts.get("active") else " TS Inactive ",
            fg_color=COLOR_SUCCESS if ts.get("active") else COLOR_MUTED_TEXT
        )
        self.views["settings"].reload_from_state()

    # =========================================================================
    # Non-Blocking Thread-Safe Event Drain (Zero Beachballs)
    # =========================================================================

    def drain_ui_events(self) -> None:
        """Main Tk thread scheduled loop polling thread-safe event queue."""
        if self.closing:
            return

        try:
            while True:
                try:
                    event_type, payload = self.event_queue.get_nowait()
                except queue.Empty:
                    break

                self._dispatch_event(event_type, payload)
        finally:
            self.after(UI_POLL_MS, self.drain_ui_events)

    def _dispatch_event(self, event_type: str, payload: any) -> None:
        """Safely update GUI widgets on main thread according to event type."""
        if event_type == "log":
            self.views["logs"].append_log_line(payload)
        elif event_type == "snippet_received":
            sender = payload.get("sender", "Peer")
            text = payload.get("text", "")
            enc = payload.get("encrypted", False)
            self.views["clipboard"].add_received_snippet(sender, text, is_encrypted=enc)
        elif event_type == "peer_scan_done":
            if self.udp_server:
                for p in payload:
                    with self.udp_server.lock:
                        self.udp_server.peers[p["ip"]] = p
            self._update_all_peer_views()
        elif event_type == "transfer_recorded":
            self.views["transfer"].refresh_queue_display()
            self.views["logs"].reload_logs()

    def _periodic_peer_refresh(self) -> None:
        """Periodically refresh active mesh peers list."""
        if self.closing:
            return
        try:
            self._update_all_peer_views()
        finally:
            self.after(PEER_REFRESH_MS, self._periodic_peer_refresh)

    def _update_all_peer_views(self) -> None:
        if not self.udp_server:
            return
        peers = self.udp_server.get_active_peers()
        self._last_peers = peers
        self.views["peers"].render_peers(peers)
        self.views["transfer"].update_peers_menu(peers)
        self.views["clipboard"].update_peers_menu(peers)

    def _periodic_metrics_refresh(self) -> None:
        """Periodically update in-flight transfer progress."""
        if self.closing:
            return
        try:
            self.views["transfer"].update_live_metrics()
        finally:
            self.after(METRICS_REFRESH_MS, self._periodic_metrics_refresh)

    # =========================================================================
    # Safe Lifecycle Shutdown
    # =========================================================================

    def on_close(self) -> None:
        """Safely shutdown background sockets and cleanly destroy window."""
        self.closing = True
        state.event_listener = None

        if self.udp_server:
            try:
                self.udp_server.stop()
            except Exception:
                pass

        try:
            stop_tcp_server()
        except Exception:
            pass

        self.destroy()
        sys.exit(0)


def launch_ui() -> None:
    """Launch the Apple-native LocalShare desktop application."""
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = LocalShareMacOSApp()
    app.mainloop()


if __name__ == "__main__":
    launch_ui()
