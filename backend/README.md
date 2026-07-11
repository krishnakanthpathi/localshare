# LocalShare Backend Server

LocalShare is a cross-platform (macOS, Windows, Linux, Mobile), zero-config, peer-to-peer (P2P) local file and folder sharing backend written in Node.js. It achieves maximum local network speeds by combining **UDP broadcasting** for automatic device discovery with **raw TCP socket streams** for actual file transfers, all controllable via a clean Express API and real-time WebSockets.

---

## 🏗️ Architecture & Protocol Design

The backend uses a modular, layered service architecture (Controller-Service-Route pattern) that cleanly separates network operations, business rules, and Express endpoint declarations.

```
┌────────────────────────────────────────────────────────┐
│                   Vite + React UI                      │
└──────────────────────────┬─────────────────────────────┘
                           │ (HTTP / WebSockets)
                           ▼
┌────────────────────────────────────────────────────────┐
│                   Express API (5050)                   │
└──────────────────────────┬─────────────────────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ UDP Service  │    │ TCP Service  │    │ Storage Serv │
│  (Port 8585) │    │  (Port 5051) │    │  (Filesystem)│
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       ▼ (LAN Broadcast)   ▼ (Direct TCP P2P)  ▼ (Local Disk)
   Local Network        Remote Device       ~/Downloads/LocalShare
```

### 1. Device Discovery (UDP Broadcast)
- **Port**: `8585` (Configurable via `UDP_PORT`)
- **Protocol**: UDP Socket Broadcast (`dgram`)
- Every 5 seconds, each device announces its identity to the local subnet broadcast address (`255.255.255.255`).
- Inbound announcements are parsed to maintain a live map of active peers on the LAN. Devices that do not announce themselves for 15 seconds are automatically pruned.

### 2. High-Speed File Transfer (Raw TCP Sockets)
- **Port**: `5051` (Configurable via `TCP_PORT`)
- **Protocol**: Custom Binary-Prefixed TCP Stream (`net`)
- Transfers bypass HTTP parsing and overhead. The connection follows this custom framing structure:

```
┌───────────────────────────┬───────────────────────────────────┬────────────────────────────────────┐
│  Header Length (4 Bytes)  │   JSON Metadata (Variable Size)   │    File Binary (Remainder)         │
│  Big-endian 32-bit uint   │  {"fileName", "fileSize", ...}    │  Raw file or zipped byte stream    │
└───────────────────────────┴───────────────────────────────────┴────────────────────────────────────┘
```

1. **Handshake**: The sender connects to the receiver's TCP port `5051` and writes the 4-byte header length, followed by the JSON metadata payload.
2. **Acceptance Control**: The receiver pauses the socket, extracts the metadata, and prompts the local user via WebSockets. If accepted, the receiver responds with `ACCEPT\n` over the TCP socket. If rejected, it responds with `REJECT\n` and closes the socket.
3. **Piping**: Upon receiving `ACCEPT`, the sender pipes the file (or a zipped folder stream) directly into the TCP socket. The receiver pipes the socket stream directly onto disk (or through an `unzipper` extraction stream).

### 3. Folder Zipping (Dynamic Compression)
- Directories and group selections are zipped on-the-fly using `archiver` before entering the TCP stream.
- The receiver detects the `isFolder: true` metadata flag and automatically pipes the incoming raw TCP stream through `unzipper` to reconstruct the folder structure recursively in their storage folder, avoiding manual extraction.

---

## 📂 macOS Storage Directory Configuration

Received files are saved to any directory on the operating system.
* **Default macOS Path**: `~/Downloads/LocalShare` (Resolves automatically to `/Users/<username>/Downloads/LocalShare`).
* **Environment Configuration**: You can change this in the `.env` file by updating `STORAGE_PATH`.
* **Dynamic Settings Configuration**: You can change the directory at runtime via the REST API. The system verifies write access to the new folder and recursively creates directories if they do not exist.

---

## 🛠️ API Documentation (HTTP REST Endpoint Guide)

### 1. Peer Discovery
* **`GET /api/peers`**
  - Returns a list of all currently active LAN devices running LocalShare.

### 2. File / Folder Sharing
* **`POST /api/peers/send`**
  - Triggers the backend to connect to a remote device and send a file or folder.
  - Body (JSON):
    ```json
    {
      "peerIp": "192.168.1.20",
      "peerPort": 5051,
      "fileName": "lecture.mp4",
      "filePath": "" 
    }
    ```
    *(Specify `filePath` for an absolute custom path, or `fileName` to look up inside the local storage directory).*

### 3. Accept/Reject Handshake
* **`POST /api/peers/transfers/:transferId/accept`**
  - Approves an incoming transfer request and starts writing to disk.
* **`POST /api/peers/transfers/:transferId/reject`**
  - Rejects an incoming transfer request and disconnects the sender.

### 4. Local File Repository
* **`GET /api/peers/files`**: List files in the local storage directory.
* **`DELETE /api/peers/files/:fileName`**: Delete a file.
* **`GET /api/peers/files/download/:fileName`**: Stream download of a file to the browser.
* **`POST /api/peers/files/upload`**: Upload multipart file data from the local browser to this device's storage folder.

### 5. Configurations
* **`GET /api/system/config`**: Get current IP, storage path, port, and device name.
* **`POST /api/system/config`**: Change storage path or device name at runtime.
  - Body (JSON):
    ```json
    {
      "storagePath": "~/Desktop/SharedReceived",
      "deviceName": "Office MacBook Pro"
    }
    ```

---

## 🚀 How to Run

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Install dependencies (if not already done):
   ```bash
   npm install
   ```
3. Run the development server (runs with `--watch` auto-reloading):
   ```bash
   npm run dev
   ```
4. Start in production mode:
   ```bash
   npm start
   ```
