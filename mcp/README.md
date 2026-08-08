# 🤖 LocalShare MCP Service

FastMCP Model Context Protocol integration enabling AI agents (Antigravity, Claude, Cursor) to interact programmatically with LocalShare mesh nodes.

## 🚀 Quick Start

```bash
# 1. Navigate to mcp folder
cd localshare/mcp

# 2. (Optional) Install dependencies
pip install -r requirements.txt

# 3. Run MCP server stdio loop
python3 mcp_server.py
```

## ⚙️ Configuration & Target Backend

Customize target backend URL or MCP port settings in `.env`:

```ini
MCP_PORT=8000
BACKEND_API_URL=http://localhost:4000
```

When running standalone, `mcp_server.py` communicates with the running backend node over REST API specified in `BACKEND_API_URL`.

## 🛠 Available MCP Tools

- `localshare_discover_peers(timeout)`: Discover active LAN / Tailscale peers.
- `localshare_send_file(target_ip, file_path)`: Send file/folder to target IP.
- `localshare_send_text(text, target_ip)`: Broadcast or send clipboard text snippet.
- `localshare_get_transfers()`: Monitor status of active transfers.
- `localshare_toggle_approval(auto_approve)`: Toggle auto-acceptance setting.
