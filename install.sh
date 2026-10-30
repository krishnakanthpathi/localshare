#!/usr/bin/env bash
# LocalShare 2.1.0 Universal Installer
# Usage: curl -sSL https://raw.githubusercontent.com/krishnakanthpathi/localshare/master/install.sh | bash

set -e

echo "🚀 Installing LocalShare 2.1.0..."

# Check Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python 3 is required but was not found. Please install Python 3 (>= 3.10) and retry."
    exit 1
fi

# Detect pip command
PIP_CMD=""
if command -v pip3 >/dev/null 2>&1; then
    PIP_CMD="pip3"
elif command -v pip >/dev/null 2>&1; then
    PIP_CMD="pip"
else
    echo "❌ pip is required but was not found. Please install python3-pip and retry."
    exit 1
fi

REPO_URL="https://github.com/krishnakanthpathi/localshare"
RAW_BASE="https://raw.githubusercontent.com/krishnakanthpathi/localshare/master"
WHEEL_NAME="localshare-2.1.0-py3-none-any.whl"
WHEEL_URL="${RAW_BASE}/dist/${WHEEL_NAME}"

# Attempt wheel download & install
TMP_DIR=$(mktemp -d 2>/dev/null || mktemp -d -t 'localshare')
TMP_WHL="${TMP_DIR}/${WHEEL_NAME}"

echo "📦 Fetching LocalShare 2.1.0 wheel package..."
if curl -sSL -f "$WHEEL_URL" -o "$TMP_WHL" 2>/dev/null && [ -s "$TMP_WHL" ]; then
    echo "📥 Installing pre-built wheel via ${PIP_CMD}..."
    $PIP_CMD install --upgrade "$TMP_WHL"
else
    echo "⚠️ Direct wheel download unavailable; installing directly from GitHub repository..."
    $PIP_CMD install --upgrade "git+${REPO_URL}.git"
fi

rm -rf "$TMP_DIR"

echo "✅ LocalShare 2.1.0 installed successfully!"

# Check if command is in PATH
if ! command -v localshare >/dev/null 2>&1; then
    if [ -f "$HOME/.local/bin/localshare" ]; then
        echo ""
        echo "💡 Notice: ~/.local/bin is not in your current PATH."
        echo "   Add it by running: export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo "   Or add that line to your ~/.bashrc or ~/.zshrc."
    fi
fi

echo ""
echo "🎉 Ready! Run 'localshare --help' or 'localshare mouse client' to start."
