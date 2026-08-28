# LocalShare 2.0 🚀

High-Speed Encrypted Mesh File & Text Sharing Architecture with Multi-Folder Queueing, Streaming Gzip Compression, AES-256-GCM Encryption, Real-Time Tailscale Resolution, 4x Parallel Sockets, FastMCP AI Tooling, and MongoDB Configuration Persistence.

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
│   │   └── stream.py          # Socket adapters & exact byte readers
│   ├── discovery/             # LAN & Tailscale Real-time Discovery
│   │   ├── __init__.py
│   │   ├── udp_beacon.py      # UDP broadcast beacon & listener
│   │   └── tailscale.py       # Real-time Tailscale status & peer resolver
│   ├── transfer/              # TCP Binary Transfer Engine
│   │   ├── __init__.py
│   │   ├── protocol.py        # Length-prefixed framing
│   │   ├── server.py          # TCP listener & secure receiver
│   │   └── client.py          # TCP sender (multi-folder, parallel & single stream)
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
├── setup.py                   # Package setup configuration
├── pyproject.toml             # Build system requirements
└── requirements.txt           # Python dependencies
```

---

## ⚡ Key Capabilities

1. **Focus on Interactive CLI**: Rich, colorful terminal dashboard with numbered menus for discovering peers, batch queuing multiple folders, managing settings, resolving Tailscale nodes, and clipboard syncing.
2. **Multi-Folder Batch Queueing**: Send multiple directories simultaneously. Preserves folder tree structures, handles sequential/parallel execution, and tracks aggregate progress, speed (MB/s), and ETA.
3. **High-Performance 4x Parallel Sockets**: Automatically segments large unencrypted files (≥10MB) into parallel chunks over 4 dedicated TCP streams with atomic non-locking `pwrite` disk writing.
4. **Streaming Gzip Compression**: High-speed on-the-fly Gzip compression (configurable levels 1–9) for rapid network throughput.
5. **End-to-End Encryption**: Authenticated AES-256-GCM chunk encryption with automatic 12-byte random nonces and 16-byte integrity tags.
6. **Real-Time Tailscale Resolution & IP Naming**: Queries Tailscale daemon status dynamically, resolves MagicDNS/IPs, and stores custom user-assigned aliases for any IP in MongoDB.
7. **MongoDB Persistence & Settings Panel**: Dynamic configuration storage in MongoDB (`pymongo`) without `.env` files. Includes interactive CLI settings editor and `/api/settings` REST endpoints.
8. **Clean Absolute Imports**: Strict `from app.xxx import yyy` references with zero `try/except` import fallback blocks.
9. **Built-in FastMCP Service**: Dedicated Model Context Protocol server exposing LocalShare tools directly to AI agents.

---

## 🔄 Complete End-to-End System Flows

LocalShare coordinates multiple asynchronous subsystems across networking, cryptography, background queue scheduling, storage persistence, and agent interfaces. Below are the complete architectural and operational data flows.

```mermaid
graph TD
    A[main.py Master Entrypoint] --> B{Execution Mode}
    B -->|python main.py| C[Interactive CLI Dashboard]
    B -->|python main.py server| D[Headless Daemon Node]
    B -->|python main.py mcp| E[FastMCP Agent Service]
    B -->|CLI Subcommand| F[Direct CLI Subcommands]

    C --> G[Subsystem Orchestration]
    D --> G
    F --> G

    subgraph Core Subsystems
        G --> H[UDP Beacon & Tailscale Discovery]
        G --> I[Multi-Folder Queue Manager]
        G --> J[TCP Server & Client Transfer Engine]
        G --> K[Gzip + AES-256-GCM Pipeline Engine]
        G --> L[OS Clipboard Synchronization]
        G --> M[MongoDB Dynamic Persistence]
        G --> N[FastAPI REST API & SSE Server]
    end
```

---

### 1. 🌐 Peer Discovery & Mesh Resolution Flow

LocalShare maintains real-time mesh awareness across both local subnet broadcasts and remote Tailscale overlay networks.

```mermaid
sequenceDiagram
    autonumber
    participant NodeA as Local Node (Sender)
    participant LAN as Local Subnet (UDP 4002)
    participant TS as Tailscale Daemon
    participant Mongo as MongoDB
    participant NodeB as Remote Peer (Receiver)

    Note over NodeA: Periodic Beacon (5s) or Manual Scan Trigger
    NodeA->>LAN: UDP Broadcast `ANNOUNCE` / `DISCOVER` (255.255.255.255, subnet.255)
    NodeA->>TS: Query `tailscale status --json`
    TS-->>NodeA: Online Tailscale Peer IPs & MagicDNS Names
    NodeA->>NodeB: Direct UDP Unicast `DISCOVER` to Tailscale IP (100.x.x.x)

    NodeB->>NodeA: UDP Unicast `RESPONSE` [Device Name, TCP Port, Web Port, Echoed Timestamp]
    
    NodeA->>Mongo: Query `peer_aliases` for IP
    Mongo-->>NodeA: Custom Friendly Name (if assigned)
    Note over NodeA: Calculate exact RTT latency = (now - timestamp) * 1000 ms
    Note over NodeA: Merge LAN & Tailscale metadata into Unified Peer List
```

**Discovery Details**:
- **Protocol**: UDP datagrams on port `4002` with JSON payloads (`DISCOVER`, `ANNOUNCE`, `RESPONSE`).
- **Precision Latency**: Echoed timestamps allow exact single-clock RTT calculation without clock skew.
- **Peer Enrichment**: IPs matching `100.x.x.x` or reported by the local Tailscale daemon receive OS metadata, hostname resolution, and Tailscale tags. Custom MongoDB aliases take highest display precedence.

---

### 2. 📦 Multi-Folder Batch Ingestion & Queue Flow

When sending files or folder trees, LocalShare preserves directory hierarchies and creates structured batch tasks.

```mermaid
flowchart TD
    A[User specifies paths: folders & files] --> B[Path Validation & Traversal]
    B --> C{Is Directory or File?}
    C -->|Single File| D[Create TransferTask: basename as rel_path]
    C -->|Directory| E[os.walk recursion: retain root folder name in relative_path]
    D --> F[Assemble into BatchTransferTask]
    E --> F
    F --> G[Assign unique batch_id UUID]
    G --> H[Register batch in TransferQueueManager]
    H --> I[Queue Worker Daemon Thread]
    I --> J{Task Execution Loop}
    J -->|Next QUEUED Task| K[Execute Single/Parallel Transfer Engine]
    K --> L[Stream Progress Callback]
    L --> M[Update Task & Aggregate Batch Metrics: Speed MB/s, ETA, Percent]
    M --> N{More Tasks in Batch?}
    N -->|Yes| J
    N -->|No| O[Mark Batch COMPLETED / Record in MongoDB]
```

**Folder Preservation Example**:
- Specifying `/data/project/` containing `src/main.py` and `docs/readme.txt` enqueues tasks with relative paths `project/src/main.py` and `project/docs/readme.txt`. The receiver creates the identical directory structure under its configured upload directory.

---

### 3. ⚡ Single-Stream Transfer & Processing Pipeline Flow

For single files or streams with encryption/compression active, data passes through a 4-byte length-prefixed streaming pipeline.

```mermaid
sequenceDiagram
    autonumber
    participant Sender as TCP Client (Sender)
    participant Receiver as TCP Server (Receiver)
    participant Disk as Target Storage

    Sender->>Receiver: TCP Connect on Port 4001
    Sender->>Receiver: Frame `FILE_HEADER` [transfer_id, filename, rel_path, filesize, is_compressed, is_encrypted, checksum]
    
    alt Auto-Approve Disabled & Suspicious Check
        Note over Receiver: Display approval prompt to user (30s timeout)
        Receiver-->>Sender: Frame `FILE_RESPONSE` [status: ACCEPT/REJECT, resume_offset]
    else Auto-Approve Enabled
        Receiver-->>Sender: Frame `FILE_RESPONSE` [status: ACCEPT, resume_offset]
    end

    Note over Sender: Open file (buffer 1MB) & Seek to resume_offset
    
    loop Stream Chunks (64 KB)
        Sender->>Sender: 1. Read raw chunk from disk
        opt If Compression Enabled
            Sender->>Sender: 2. zlib.compressobj(level) Deflate
        end
        opt If Encryption Enabled
            Sender->>Sender: 3. AES-256-GCM Encrypt: [12B Nonce][Ciphertext + 16B Tag]
        end
        Sender->>Receiver: Binary Frame: [4-Byte Chunk Length][Payload Chunk]
        
        Receiver->>Receiver: 1. Read exact 4-byte chunk header
        opt If Encryption Enabled
            Receiver->>Receiver: 2. AES-256-GCM Decrypt & Authenticate Tag
        end
        opt If Compression Enabled
            Receiver->>Receiver: 3. zlib.decompressobj() Inflate
        end
        Receiver->>Disk: Write chunk to disk & Update MD5 hasher
        Note over Sender,Receiver: Calculate instantaneous speed (1.5s rolling window) & ETA
    end

    Sender->>Receiver: End of Stream Marker [4-Byte Zero Length: 0x00000000]
    Receiver->>Receiver: Validate Checksum & File Size
    Receiver-->>Sender: Frame `TRANSFER_COMPLETE` [status: SUCCESS, received_bytes]
    Note over Sender,Receiver: Record Transfer in MongoDB & Close Sockets
```

---

### 4. 🚀 4x Multi-Socket Parallel Streaming Architecture

Large unencrypted files (≥10MB) automatically activate 4 concurrent TCP worker sockets for maximum throughput over Gigabit LAN and high-speed mesh networks.

```mermaid
sequenceDiagram
    autonumber
    participant Client as Sender Control Engine
    participant Workers as 4x Sender Workers
    participant Server as Receiver Control Engine
    participant TargetFile as Receiver Disk (pwrite)

    Client->>Server: TCP Connect (Control Socket)
    Client->>Server: Frame `PARALLEL_FILE_HEADER` [transfer_id, filesize, num_parts: 4, parts: offsets & lengths, checksum]
    Server->>TargetFile: Secure Safe Join & `os.ftruncate(fd, filesize)` pre-allocation
    Server-->>Client: Frame `PARALLEL_FILE_RESPONSE` [status: ACCEPT, num_parts: 4]

    par 4 Concurrent Stream Workers
        Workers->>Server: Worker 0 Connect & Send `PART_STREAM_HEADER` [part: 0, offset: 0, length: L0]
        Server-->>Workers: `PART_RESPONSE` [status: READY]
        Workers->>TargetFile: Stream Chunks -> `os.pwrite(fd, chunk, offset)`
    and
        Workers->>Server: Worker 1 Connect & Send `PART_STREAM_HEADER` [part: 1, offset: O1, length: L1]
        Server-->>Workers: `PART_RESPONSE` [status: READY]
        Workers->>TargetFile: Stream Chunks -> `os.pwrite(fd, chunk, offset)`
    and
        Workers->>Server: Worker 2 Connect & Send `PART_STREAM_HEADER` [part: 2, offset: O2, length: L2]
        Server-->>Workers: `PART_RESPONSE` [status: READY]
        Workers->>TargetFile: Stream Chunks -> `os.pwrite(fd, chunk, offset)`
    and
        Workers->>Server: Worker 3 Connect & Send `PART_STREAM_HEADER` [part: 3, offset: O3, length: L3]
        Server-->>Workers: `PART_RESPONSE` [status: READY]
        Workers->>TargetFile: Stream Chunks -> `os.pwrite(fd, chunk, offset)`
    end

    loop Out-of-Band Synchronization
        Server-->>Client: Out-of-band `PROGRESS_ACK` on Control Socket [received_bytes, filesize]
        Note over Client,Server: Live sync progress % and throughput metrics across all workers
    end

    Note over Server: All 4 parts completed -> Close file descriptor
    Server-->>Client: Frame `TRANSFER_COMPLETE` [status: SUCCESS, received_bytes: filesize]
    Note over Client,Server: Persist Completed Transfer to MongoDB
```

**Key Parallel Architecture Features**:
- **Atomic Zero-Lock Disk Writes**: `os.pwrite(fd, chunk, offset)` writes directly to the pre-allocated file at exact byte offsets without file-lock contention across threads.
- **Out-of-Band Control Protocol**: Live progress updates and checksum confirmations travel over a dedicated control socket, keeping the UI dashboard in sync.

---

### 5. 🛡️ Security, Encryption & Integrity Verification Flow

LocalShare implements authenticated symmetric encryption and strict path sandboxing.

```mermaid
flowchart LR
    subgraph Sender Cryptographic Engine
        A[Plaintext Chunk] --> B[Generate 12-byte Random Nonce]
        B --> C[AES-256-GCM AEAD Encrypt with 32-byte Key]
        C --> D[Assemble: Nonce 12B + Ciphertext + Auth Tag 16B]
    end

    D -->|TCP Socket Binary Frame| E[Encrypted Wire Payload]

    subgraph Receiver Cryptographic Engine
        E --> F[Extract 12-byte Nonce & 16-byte Auth Tag]
        F --> G[AES-256-GCM Decrypt & Integrity Verification]
        G -->|Tag Valid| H[Decrypted Plaintext Chunk]
        G -->|Tag Invalid / Corrupt| I[Abort Transfer: Decryption Error]
    end
```

**Security Guarantees**:
- **AES-256-GCM Authenticated Encryption**: Every chunk has a distinct 96-bit random nonce (`os.urandom(12)`) and a 128-bit authentication tag ensuring confidentiality and tamper resistance.
- **Key Derivation**: Passphrases automatically derive 256-bit keys via `PBKDF2HMAC` with `SHA256` and 100,000 iterations.
- **Directory Traversal Protection**: All paths are validated via `safe_join()` to prevent `../` path escape vulnerabilities. Suspicious file extensions (`.sh`, `.bat`, `.exe`, etc.) trigger security alerts.

---

### 6. 📋 Clipboard Synchronization & Text Broadcast Flow

LocalShare seamlessly synchronizes text and clipboard contents across platforms.

```mermaid
sequenceDiagram
    autonumber
    participant CLI as CLI / Web UI / MCP Agent
    participant Sync as app/sync/clipboard.py
    participant OS as OS Native Clipboard (pbcopy / xclip / powershell)
    participant Client as TCP Client
    participant Peer as Remote Peer TCP Server
    participant Mongo as MongoDB

    CLI->>Sync: `broadcast_text(text)` or `send_text_snippet(target_ip, text)`
    opt If text not provided
        Sync->>OS: Read current clipboard (pbpaste / xclip / Get-Clipboard)
        OS-->>Sync: Plaintext String
    end

    opt If Encryption Enabled
        Sync->>Sync: Encrypt text with AES-256-GCM -> Base64 payload
    end

    Sync->>Client: Open TCP connection to target peer(s) on port 4001
    Client->>Peer: Send Frame `TEXT_SNIPPET` [text, sender, is_encrypted, timestamp]
    
    opt If Encrypted
        Peer->>Peer: Decrypt Base64 payload with shared AES key
    end

    Peer->>OS: Write to receiver's system clipboard
    Peer->>Mongo: Record snippet in `clipboard` collection
    Note over Peer: Push snippet to Live In-Memory Clipboard History
```

---

### 7. 🍃 MongoDB Dynamic Persistence & Configuration Flow

LocalShare uses MongoDB for zero-configuration persistence without `.env` files, featuring graceful offline caching and connection throttling.

```mermaid
flowchart TD
    A[LocalShare Startup / Action] --> B{MongoDB Connected?}
    B -->|Yes| C[Read/Write directly to MongoDB Collections]
    B -->|No / Cooldown Active| D[Fallback to In-Memory Runtime State]
    
    subgraph MongoDB Collections
        C --> E[settings: App settings, auto-approve, crypto keys, upload dir]
        C --> F[peer_aliases: Custom IP-to-friendly-name mappings & notes]
        C --> G[transfers: Historical inbound and outbound transfer logs]
        C --> H[clipboard: Shared text snippets and timestamped sync history]
    end

    D --> I[Automatic 15-second retry cooldown to prevent connection stalls]
```

---

### 8. 🤖 FastMCP AI Agent Tool Execution Flow

LocalShare embeds a full FastMCP (Model Context Protocol) server for autonomous AI agent control.

```mermaid
sequenceDiagram
    autonumber
    participant Agent as AI Coding Agent / LLM
    participant MCP as FastMCP Server (app/mcp/server.py)
    participant Core as LocalShare Core Modules
    participant Mesh as Network Mesh / Mongo DB

    Agent->>MCP: Call `localshare_discover_peers(timeout=2.0)`
    MCP->>Core: Trigger `discover_peers()`
    Core->>Mesh: Query LAN UDP & Tailscale Daemon
    Mesh-->>Core: Active peer records
    Core-->>MCP: Peer list with friendly names & latency
    MCP-->>Agent: JSON Response with discovered peers

    Agent->>MCP: Call `localshare_queue_folders_and_files(target_ip, paths)`
    MCP->>Core: `queue_manager.enqueue_paths(...)`
    Core-->>MCP: `BatchTransferTask` created [batch_id, file_count, total_bytes]
    MCP-->>Agent: Return batch execution confirmation
```

**Available MCP Tools**:
- `localshare_discover_peers`: Discover active LAN & Tailscale peers.
- `localshare_get_tailscale_status`: Query real-time Tailscale network diagnostics.
- `localshare_queue_folders_and_files`: Queue multiple folders and files simultaneously.
- `localshare_get_queue_status`: Query active, queued, and completed transfer batches.
- `localshare_send_text`: Share text snippet or broadcast to all mesh peers.
- `localshare_set_peer_name`: Store custom friendly name for an IP in MongoDB.
- `localshare_get_settings` / `localshare_update_settings`: Manage runtime configuration.
- `localshare_generate_encryption_key`: Generate a cryptographically secure AES-256 key.

---

### 9. 🌐 REST API & Real-Time SSE Event Stream Flow

The built-in FastAPI web server exposes a REST interface and real-time Server-Sent Events (SSE) stream for web clients, scripts, and mobile browsers.

```mermaid
flowchart TD
    Client[Web Browser / Mobile Client / Automation Script] --> API[FastAPI Web Server :4000]
    
    subgraph REST Endpoints
        API -->|GET /api/events| SSE[Server-Sent Events Stream: Real-Time Transfers & Batches]
        API -->|GET /api/peers| P[Discover Active LAN & Tailscale Peers]
        API -->|GET, POST /api/settings| S[Settings & Configuration Manager]
        API -->|GET, POST /api/settings/peers| A[Custom Peer Aliases & Notes]
        API -->|GET, POST /api/queue/*| Q[Multi-Folder Queue: Enqueue, Pause, Resume, Cancel]
        API -->|GET, POST /api/transfers| T[Active Transfers & MongoDB History]
        API -->|GET, POST /api/clipboard| C[Clipboard Read, Write & Network Broadcast]
        API -->|POST /api/upload| U[HTTP Multipart File Upload]
        API -->|GET /api/download/{path}| D[File & Compressed Folder Download]
        API -->|GET /api/qrcode| QR[SVG QR Code for Instant Mobile Pairing]
    end
```

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

# Run FastMCP service for AI agents
python main.py mcp
```

