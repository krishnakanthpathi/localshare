# ⚙️ LocalShare Backend

The high-performance FastAPI, TCP transfer, and UDP discovery engine for LocalShare.

## 🚀 Quick Start

```bash
# 1. Navigate to backend
cd localshare/backend

# 2. (Optional) Install dependencies
pip install -r requirements.txt

# 3. Start backend server
python3 main.py
```

## ⚙️ Environment Variables & Custom Ports

You can customize port numbers, host address, and storage directories by editing `.env` or exporting environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | Host IP address to bind server |
| `WEB_PORT` | `4000` | FastAPI Web & REST API HTTP port |
| `TCP_PORT` | `4001` | Multi-socket binary transfer port |
| `UDP_PORT` | `41234` | UDP Auto-discovery beacon port |
| `UPLOAD_DIR` | `~/Downloads/LocalShare` | Target folder for incoming downloads |

Example with custom ports:
```bash
WEB_PORT=8080 TCP_PORT=8081 python3 main.py
```

## 🧪 Running Backend Unit Tests

```bash
python3 -m unittest tests/test_localshare.py
```
