"""
Settings & Security Preferences View
Configures Device Name, Storage Paths, Gzip Compression, AES-256 Keys, and Tailscale.
"""

from __future__ import annotations

import os
import subprocess
from tkinter import filedialog, messagebox
import customtkinter as ctk

from app.ui.constants import (
    PAD_XS, PAD_SM, PAD_MD, PAD_LG, PAD_XL,
    RADIUS_TAG, RADIUS_CONTROL, RADIUS_CARD,
    COLOR_ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_MUTED_TEXT,
    COLOR_CARD_BG, COLOR_BORDER, COLOR_INSET_BG
)
from app.config import state, CONFIG_FILE, LOG_FILE
from app.storage import load_settings, save_settings
from app.security.encryption import generate_key
from app.discovery.tailscale import get_tailscale_status


class SettingsView(ctk.CTkScrollableFrame):
    """Preferences and Security configuration panel."""

    def __init__(self, parent, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._setup_ui()
        self.reload_from_state()

    def _setup_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        # 1. Device Identity Card
        card_identity = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        card_identity.pack(fill="x", padx=PAD_LG, pady=(PAD_LG, PAD_SM))
        card_identity.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_identity,
            text="DEVICE IDENTITY",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_MUTED_TEXT
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))

        ctk.CTkLabel(
            card_identity,
            text="Device Name:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=1, column=0, padx=PAD_MD, pady=PAD_SM, sticky="w")

        self.entry_device_name = ctk.CTkEntry(
            card_identity,
            height=32,
            corner_radius=RADIUS_CONTROL
        )
        self.entry_device_name.grid(row=1, column=1, sticky="ew", padx=PAD_SM, pady=PAD_SM)

        self.btn_save_name = ctk.CTkButton(
            card_identity,
            text="Update Name",
            width=110,
            height=32,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            command=self._on_save_device_name
        )
        self.btn_save_name.grid(row=1, column=2, padx=PAD_MD, pady=PAD_SM)

        # 2. File Transfers & Storage Card
        card_storage = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        card_storage.pack(fill="x", padx=PAD_LG, pady=PAD_SM)
        card_storage.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_storage,
            text="STORAGE & TRANSFERS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_MUTED_TEXT
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))

        ctk.CTkLabel(
            card_storage,
            text="Download Folder:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=1, column=0, padx=PAD_MD, pady=PAD_SM, sticky="w")

        self.lbl_upload_dir = ctk.CTkLabel(
            card_storage,
            text=state.upload_dir,
            font=ctk.CTkFont(family="Courier New", size=11),
            anchor="w"
        )
        self.lbl_upload_dir.grid(row=1, column=1, sticky="ew", padx=PAD_SM, pady=PAD_SM)

        self.btn_browse_dir = ctk.CTkButton(
            card_storage,
            text="Choose Folder...",
            width=130,
            height=32,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            command=self._on_choose_upload_dir
        )
        self.btn_browse_dir.grid(row=1, column=2, padx=PAD_MD, pady=PAD_SM)

        # Auto-Approve Switch
        ctk.CTkLabel(
            card_storage,
            text="Auto-Approve Files:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=2, column=0, padx=PAD_MD, pady=PAD_SM, sticky="w")

        self.switch_auto_approve = ctk.CTkSwitch(
            card_storage,
            text="Accept incoming files automatically from mesh peers",
            command=self._on_toggle_auto_approve
        )
        self.switch_auto_approve.grid(row=2, column=1, columnspan=2, sticky="w", padx=PAD_SM, pady=PAD_SM)

        # 3. Compression Engine Card
        card_compress = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        card_compress.pack(fill="x", padx=PAD_LG, pady=PAD_SM)
        card_compress.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_compress,
            text="GZIP COMPRESSION ENGINE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_MUTED_TEXT
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))

        self.switch_compression = ctk.CTkSwitch(
            card_compress,
            text="Enable streaming Gzip compression for compressible files",
            command=self._on_toggle_compression
        )
        self.switch_compression.grid(row=1, column=0, columnspan=3, sticky="w", padx=PAD_MD, pady=PAD_SM)

        ctk.CTkLabel(
            card_compress,
            text="Compression Level:",
            font=ctk.CTkFont(size=13)
        ).grid(row=2, column=0, padx=PAD_MD, pady=PAD_SM, sticky="w")

        self.slider_compression = ctk.CTkSlider(
            card_compress,
            from_=1,
            to=9,
            number_of_steps=8,
            command=self._on_slider_compression
        )
        self.slider_compression.grid(row=2, column=1, sticky="ew", padx=PAD_SM, pady=PAD_SM)

        self.lbl_compress_val = ctk.CTkLabel(
            card_compress,
            text=f"Level {state.compression_level}",
            width=70,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_compress_val.grid(row=2, column=2, padx=PAD_MD, pady=PAD_SM)

        # 4. Security & Encryption Card
        card_crypto = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        card_crypto.pack(fill="x", padx=PAD_LG, pady=PAD_SM)
        card_crypto.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_crypto,
            text="END-TO-END AES-256-GCM ENCRYPTION",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_MUTED_TEXT
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))

        self.switch_encryption = ctk.CTkSwitch(
            card_crypto,
            text="Enable AES-256-GCM payload encryption for transfers and snippets",
            command=self._on_toggle_encryption
        )
        self.switch_encryption.grid(row=1, column=0, columnspan=3, sticky="w", padx=PAD_MD, pady=PAD_SM)

        ctk.CTkLabel(
            card_crypto,
            text="AES Key:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=2, column=0, padx=PAD_MD, pady=PAD_SM, sticky="w")

        self.entry_key = ctk.CTkEntry(
            card_crypto,
            height=32,
            font=ctk.CTkFont(family="Courier New", size=11),
            corner_radius=RADIUS_CONTROL,
            show="*"
        )
        self.entry_key.grid(row=2, column=1, sticky="ew", padx=PAD_SM, pady=PAD_SM)

        key_btn_box = ctk.CTkFrame(card_crypto, fg_color="transparent")
        key_btn_box.grid(row=2, column=2, padx=PAD_MD, pady=PAD_SM)

        self.btn_gen_key = ctk.CTkButton(
            key_btn_box,
            text="Generate",
            width=80,
            height=32,
            corner_radius=RADIUS_CONTROL,
            fg_color=COLOR_ACCENT,
            command=self._on_generate_key
        )
        self.btn_gen_key.pack(side="left", padx=(0, PAD_XS))

        self.btn_save_key = ctk.CTkButton(
            key_btn_box,
            text="Save Key",
            width=80,
            height=32,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_ACCENT,
            command=self._on_save_key
        )
        self.btn_save_key.pack(side="left")

        # 5. Tailscale Overlay Network Card
        card_ts = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        card_ts.pack(fill="x", padx=PAD_LG, pady=PAD_SM)
        card_ts.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_ts,
            text="TAILSCALE OVERLAY NETWORK",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_MUTED_TEXT
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))

        self.lbl_ts_status = ctk.CTkLabel(
            card_ts,
            text="Checking Tailscale daemon...",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.lbl_ts_status.grid(row=1, column=0, columnspan=2, sticky="w", padx=PAD_MD, pady=PAD_SM)

        self.btn_refresh_ts = ctk.CTkButton(
            card_ts,
            text="Refresh",
            width=80,
            height=28,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_MUTED_TEXT,
            command=self.refresh_tailscale_diagnostics
        )
        self.btn_refresh_ts.grid(row=1, column=2, padx=PAD_MD, pady=PAD_SM, sticky="e")

        # 6. System File Locations Card
        card_files = ctk.CTkFrame(self, corner_radius=RADIUS_CARD, fg_color=COLOR_CARD_BG)
        card_files.pack(fill="x", padx=PAD_LG, pady=(PAD_SM, PAD_LG))
        card_files.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_files,
            text="SYSTEM STORAGE PATHS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=COLOR_MUTED_TEXT
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=PAD_MD, pady=(PAD_MD, PAD_SM))

        ctk.CTkLabel(
            card_files,
            text=f"Config: {CONFIG_FILE}\nLogs:   {LOG_FILE}",
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color=COLOR_MUTED_TEXT,
            justify="left",
            anchor="w"
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=PAD_MD, pady=PAD_SM)

        self.btn_open_finder = ctk.CTkButton(
            card_files,
            text="Reveal in Finder",
            width=130,
            height=32,
            corner_radius=RADIUS_CONTROL,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_ACCENT,
            command=self._on_reveal_in_finder
        )
        self.btn_open_finder.grid(row=1, column=2, padx=PAD_MD, pady=PAD_SM, sticky="e")

        self.refresh_tailscale_diagnostics()

    def reload_from_state(self) -> None:
        """Sync UI controls with runtime AppState."""
        load_settings()
        self.entry_device_name.delete(0, "end")
        self.entry_device_name.insert(0, state.device_name)

        self.lbl_upload_dir.configure(text=state.upload_dir)

        if state.auto_approve:
            self.switch_auto_approve.select()
        else:
            self.switch_auto_approve.deselect()

        if state.compression_enabled:
            self.switch_compression.select()
        else:
            self.switch_compression.deselect()

        self.slider_compression.set(state.compression_level)
        self.lbl_compress_val.configure(text=f"Level {state.compression_level}")

        if state.encryption_enabled:
            self.switch_encryption.select()
        else:
            self.switch_encryption.deselect()

        self.entry_key.delete(0, "end")
        if state.encryption_key:
            self.entry_key.insert(0, state.encryption_key)

    def _on_save_device_name(self) -> None:
        name = self.entry_device_name.get().strip()
        if name:
            save_settings({"device_name": name})
            self.app.on_settings_updated()
            self.btn_save_name.configure(text="Saved!")
            self.after(1500, lambda: self.btn_save_name.configure(text="Update Name"))

    def _on_choose_upload_dir(self) -> None:
        d = filedialog.askdirectory(title="Choose LocalShare Download Folder", initialdir=state.upload_dir)
        if d:
            save_settings({"upload_dir": os.path.abspath(d)})
            self.lbl_upload_dir.configure(text=state.upload_dir)
            self.app.on_settings_updated()

    def _on_toggle_auto_approve(self) -> None:
        val = bool(self.switch_auto_approve.get())
        save_settings({"auto_approve": val})
        self.app.on_settings_updated()

    def _on_toggle_compression(self) -> None:
        val = bool(self.switch_compression.get())
        save_settings({"compression_enabled": val})
        self.app.on_settings_updated()

    def _on_slider_compression(self, val: float) -> None:
        lvl = int(val)
        self.lbl_compress_val.configure(text=f"Level {lvl}")
        save_settings({"compression_level": lvl})
        self.app.on_settings_updated()

    def _on_toggle_encryption(self) -> None:
        val = bool(self.switch_encryption.get())
        if val and not state.encryption_key:
            new_key = generate_key()
            self.entry_key.delete(0, "end")
            self.entry_key.insert(0, new_key)
            save_settings({"encryption_key": new_key, "encryption_enabled": True})
        else:
            save_settings({"encryption_enabled": val})
        self.app.on_settings_updated()

    def _on_generate_key(self) -> None:
        new_key = generate_key()
        self.entry_key.delete(0, "end")
        self.entry_key.insert(0, new_key)
        save_settings({"encryption_key": new_key, "encryption_enabled": True})
        self.switch_encryption.select()
        self.app.on_settings_updated()
        self.btn_gen_key.configure(text="Done!")
        self.after(1500, lambda: self.btn_gen_key.configure(text="Generate"))

    def _on_save_key(self) -> None:
        k = self.entry_key.get().strip()
        save_settings({"encryption_key": k, "encryption_enabled": bool(k)})
        if k:
            self.switch_encryption.select()
        else:
            self.switch_encryption.deselect()
        self.app.on_settings_updated()
        self.btn_save_key.configure(text="Saved!")
        self.after(1500, lambda: self.btn_save_key.configure(text="Save Key"))

    def refresh_tailscale_diagnostics(self) -> None:
        ts = get_tailscale_status()
        if not ts.get("active"):
            self.lbl_ts_status.configure(
                text="⚪ Tailscale Daemon: Inactive / Not Detected",
                text_color=COLOR_MUTED_TEXT
            )
        else:
            self_node = ts.get("Self", {})
            ip = self_node.get("TailscaleIPs", ["None"])[0]
            host = self_node.get("HostName", "Node")
            self.lbl_ts_status.configure(
                text=f"🟢 Tailscale Active • Host: {host} • IP: {ip}",
                text_color=COLOR_SUCCESS[1]
            )

    def _on_reveal_in_finder(self) -> None:
        folder = os.path.dirname(CONFIG_FILE)
        try:
            subprocess.run(["open", folder], check=False)
        except Exception:
            pass
