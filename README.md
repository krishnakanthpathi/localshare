# LocalShare 🚀

An enterprise-grade, peer-to-peer **LocalShare** engine for instant file, folder, and clipboard/text sharing across local Wi-Fi, Ethernet, and Tailscale mesh networks.

---

## 📁 Repository Structure

LocalShare is bifurcated into three distinct, independent sub-folders:

```
localshare/
├── ⚙️ backend/       # FastAPI REST API, TCP transfer engine, UDP discovery
├── 💻 frontend/      # React 19 + Vite + TailwindCSS Web UI
└── 🤖 mcp/           # FastMCP Model Context Protocol integration server
```

Each folder has its own configuration (`.env`), entry points, scripts, and documentation so that services can be configured and run independently on different ports and hosts.

---

## ⚙️ 1. Backend (`localshare/backend`)

The backend powers FastAPI HTTP REST endpoints, multi-socket TCP file streaming, and UDP discovery beacons.

```bash
cd localshare/backend
python3 main.py
```

### Environment Settings (`localshare/backend/.env`)
```ini
HOST=0.0.0.0
WEB_PORT=4000
TCP_PORT=4001
UDP_PORT=41234
UPLOAD_DIR=~/Downloads/LocalShare
```

---

## 💻 2. Frontend (`localshare/frontend`)

The frontend is a modern dark-mode React 19 web interface built with Vite.

```bash
cd localshare/frontend
npm install
npm run dev
```

### Environment Settings (`localshare/frontend/.env`)
```ini
VITE_PORT=5173
VITE_API_BASE_URL=http://localhost:4000
```

---

## 🤖 3. MCP Service (`localshare/mcp`)

The Model Context Protocol (FastMCP) server enables AI agents to discover peers, send files, and manage transfers.

```bash
cd localshare/mcp
python3 mcp_server.py
```

### Environment Settings (`localshare/mcp/.env`)
```ini
MCP_PORT=8000
BACKEND_API_URL=http://localhost:4000
```

---

## 🧪 Running Unit Tests

To run automated unit & integration tests across the backend and MCP modules:

```bash
python3 -m unittest discover -s localshare/backend/tests
```
