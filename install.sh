#!/usr/bin/env bash
# Quick 1-Step Installer for LocalShare Terminal App

set -e

echo "🚀 Installing LocalShare 2.0..."
python3 -m pip install --upgrade pip
python3 -m pip install -e .

echo ""
echo "✅ LocalShare successfully installed!"
echo "👉 Type 'localshare' in any terminal window to start."
