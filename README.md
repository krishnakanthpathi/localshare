# LocalShare 2.0 🚀

High-Speed Encrypted Mesh File & Text Sharing Architecture with Multi-Folder Queueing, Streaming Gzip Compression, AES-256-GCM Encryption, Real-Time Tailscale Resolution, and MongoDB Configuration Persistence.

---

## 🏗️ Architecture

```
localshare/
├── app/
│   ├── __init__.py
│   ├── config.py              # Runtime settings & state (no .env files)
│   ├── utils.py               # Networking, path security, QR codes
│   ├── db/                    # MongoDB Persistence Layer
│   │   ├── __init__.py
│   │   └── mongo.py           # Settings, peer aliases, transfers & clipboard
│   ├── security/              # Cryptography & Security
│   │   ├── __init__.py
│   │   └── encryption.py      # AES-256-GCM chunk encryption & key derivation
│   ├── queue/                 # Multi-Folder Queueing Subsystem
│   │   ├── __init__.py
│   │   ├── models.py          # TransferTask, BatchTransferTask, Statuses
│   │   └── manager.py         # Multi-folder expansion & concurrency scheduler
│   ├── processing/            # Processing Subsystem
│   │   ├── __init__.py
│   │   ├── engine.py          # Streaming Gzip compression & AES chunk pipeline
│   │   └── stream.py          # Socket adapters
│   ├── discovery/             # LAN & Tailscale Real-time Discovery
│   │   ├── __init__.py
│   │   ├── udp_beacon.py      # UDP broadcast beacon & listener
│   │   └── tailscale.py       # Real-time Tailscale status & peer resolver
│   ├── transfer/              # TCP Binary Transfer Engine
│   │   ├── __init__.py
│   │   ├── protocol.py        # Length-prefixed framing
│   │   ├── server.py          # TCP listener & secure receiver
│   │   └── client.py          # TCP sender (multi-folder & file streaming)
│   ├── sync/                  # Clipboard Sync
│   │   ├── __init__.py
│   │   └── clipboard.py       # OS clipboard helpers & text broadcast
│   ├── api/                   # Web API & Settings Endpoints
│   │   ├── __init__.py
│   │   ├── routes.py          # REST endpoints (/api/settings, /api/queue, etc.)
│   │   └── server.py          # FastAPI app factory & server runner
│   ├── mcp/                   # Model Context Protocol Service
│   │   ├── __init__.py
│   │   ├── config.py          # MCP service configuration
│   │   └── server.py          # FastMCP server & tools
│   └── cli/                   # Command Line Interface
│       ├── __init__.py
│       └── main.py            # Rich interactive terminal dashboard & commands
├── main.py                    # Master CLI / Server / MCP entrypoint
└── requirements.txt           # Python dependencies
```

---

## ⚡ Key Capabilities

1. **Focus on Interactive CLI**: Rich, colorful terminal dashboard with numbered menus for discovering peers, batch queuing multiple folders, managing settings, resolving Tailscale nodes, and clipboard syncing.
2. **Multi-Folder Batch Queueing**: Send multiple directories simultaneously. Preserves folder tree structures, handles sequential/parallel execution, and tracks aggregate progress, speed (MB/s), and ETA.
3. **Streaming Gzip Compression**: High-speed on-the-fly Gzip compression (configurable levels 1-9) for rapid network throughput.
4. **End-to-End Encryption**: Authenticated AES-256-GCM chunk encryption with automatic 12-byte random nonces and 16-byte integrity tags.
5. **Real-Time Tailscale Resolution & IP Naming**: Queries Tailscale daemon status dynamically, resolves MagicDNS/IPs, and stores custom user-assigned aliases for any IP in MongoDB.
6. **MongoDB Persistence & Settings Panel**: Dynamic configuration storage in MongoDB (`pymongo`) without `.env` files. Includes interactive CLI settings editor and `/api/settings` REST endpoints.
7. **Clean Absolute Imports**: Strict `from app.xxx import yyy` references with zero `try/except` import fallback blocks.
8. **Built-in FastMCP Service**: Dedicated Model Context Protocol server exposing LocalShare tools directly to AI agents.

---

## 🚀 Getting Started

### Installation
```bash
pip install -r requirements.txt
```

### Launch Interactive CLI Dashboard
```bash
python main.py
```

### CLI Subcommands
```bash
# Scan LAN and Tailscale mesh for peers
python main.py scan

# Send multiple folders and files to a peer
python main.py send /path/to/folder1 /path/to/folder2 /path/to/file.pdf --target 100.64.0.5

# Assign a custom friendly name to an IP in MongoDB
python main.py alias 100.64.0.5 "Living Room Mac" --notes "Tailscale node"

# View Tailscale mesh status
python main.py tailscale

# Broadcast or send a text snippet
python main.py text "Hello LocalShare!" --target 192.168.1.50

# Run headless server
python main.py server

# Run FastMCP service
python main.py mcp
```
