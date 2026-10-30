"""
Apple Human Interface Guidelines (HIG) Design Tokens & Constants
for LocalShare macOS Desktop App.
"""

from __future__ import annotations

# --- 8-Point Spatial Grid ---
PAD_XS = 4    # Micro-spacing, icon-to-label gaps
PAD_SM = 8    # Standard intra-component padding
PAD_MD = 12   # Card inner padding, input margin
PAD_LG = 16   # Section spacing, main window borders
PAD_XL = 24   # Major layout separation

# --- Corner Radii ---
RADIUS_TAG = 6       # Pills, tags, status badges
RADIUS_CONTROL = 8   # Buttons, text inputs, segmented items
RADIUS_CARD = 12     # Panels, cards, modal sheets
RADIUS_MODAL = 16    # Floating sheets / alert cards

# --- Apple Semantic Color Palette (Light, Dark) ---
COLOR_ACCENT = ("#007AFF", "#0A84FF")            # macOS System Blue
COLOR_ACCENT_HOVER = ("#0062CC", "#0071E3")
COLOR_DESTRUCTIVE = ("#FF3B30", "#FF453A")       # macOS Red
COLOR_DESTRUCTIVE_HOVER = ("#D32F2F", "#C62828")
COLOR_SUCCESS = ("#34C759", "#30D158")           # macOS Green
COLOR_WARNING = ("#FF9500", "#FF9F0A")           # macOS Orange
COLOR_MUTED_TEXT = ("#8E8E93", "#98989D")        # macOS Secondary Label
COLOR_TEXT_PRIMARY = ("#1C1C1E", "#F2F2F7")

# --- Background & Surface Tiers (Light, Dark) ---
COLOR_CANVAS_BG = ("#F2F2F7", "#1C1C1E")         # Window background
COLOR_CARD_BG = ("#FFFFFF", "#2C2C2E")           # Elevated panels
COLOR_INSET_BG = ("#E5E5EA", "#242426")          # Nested inputs & textboxes
COLOR_SECONDARY_CARD = ("#F8F9FA", "#323235")    # Subtle card tint
COLOR_BORDER = ("#D1D1D6", "#38383A")            # Subtle dividers
COLOR_SIDEBAR_BG = ("#EAEAEA", "#18181A")        # Sidebar column
COLOR_SIDEBAR_ACTIVE = ("#D0D0D5", "#28282C")

# --- Timing & Concurrency Intervals ---
UI_POLL_MS = 40          # 25 FPS UI event drain loop
STREAM_FLUSH_MS = 60     # Log/Output chunk stream buffer flush
PEER_REFRESH_MS = 3000   # Mesh discovery polling interval
METRICS_REFRESH_MS = 200 # Transfer progress polling interval
