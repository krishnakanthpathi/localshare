# LocalShare 🚀

An enterprise-grade, peer-to-peer **LocalShare** engine for instant file, folder, and clipboard/text sharing across local Wi-Fi, Ethernet, and Tailscale mesh networks.

## ✨ Features

- **🌐 Binding & IP Routing**: Binds to `0.0.0.0` across all interfaces (Local WiFi `192.168.x.x` & Tailscale `100.x.x.x`).
- **📡 UDP Auto-Discovery**: Automatic device discovery on port `41234` with broadcast and active scan capabilities.
- **⏩ Resumable Multi-Socket TCP Transfer**: Efficient binary protocol supporting chunk streaming, checksum verification, and resumable partial transfers.
- **📁 Directory Tree Preservation**: Batch upload entire folder structures while maintaining nested file hierarchies.
- **📋 Real-Time Clipboard & Text Sync**: Instantly broadcast code snippets and copy text between devices.
- **📱 Zero-Install Web Client & QR Code**: Embedded HTTP server serving a modern dark-mode web application (`http://<IP>:4000`) with ANSI and SVG QR code generation for instant mobile browser connection.
- **🛡️ Security & Malware Protection**: Directory traversal sanitization (`../` blocking) and suspicious executable file warnings.
- **⚡ Smart On-The-Fly Compression**: Dynamic `gzip` stream compression for text, code, logs, and uncompressed folder streams.
- **🔔 Receive Approval Toggle**: Auto-accept or prompt confirmation modal before downloading incoming transfers.
- **🤖 Native MCP Tool Server**: Standard Model Context Protocol integration (`python main.py mcp`) allowing AI agents (like Antigravity / Claude) to discover peers, send files, sync clipboard text, and monitor transfers programmatically.

---

## 🚀 Quick Start

### 1. Start Server Node (CLI + Web UI)
```bash
cd localshare
python3 main.py
# or
python3 main.py server
```

Access the Web UI from any phone or computer on the network at `http://<YOUR_IP>:4000` or scan the terminal QR code.

### 2. Scan Network for Peers
```bash
python3 main.py scan
```

### 3. Send File or Folder via CLI
```bash
python3 main.py send /path/to/my_file.pdf --target 192.168.1.50
```

### 4. Broadcast Text Snippet
```bash
python3 main.py text "Hello LocalShare Mesh!"
```

### 5. Run MCP Tool Server (for AI Agents)
```bash
python3 main.py mcp
```

---

## 🧪 Running Unit Tests

```bash
python3 -m unittest localshare/tests/test_localshare.py
```
