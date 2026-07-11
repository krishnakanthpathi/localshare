# LocalShare 🚀

LocalShare is a cross-platform (macOS, Windows, Linux, Mobile), zero-configuration, peer-to-peer (P2P) local file and folder sharing application. It achieves high local network speeds by utilizing **UDP broadcasting** for automatic device discovery, and **raw TCP socket streams** for direct file transfers. 

Features a modern, responsive React web interface styled with glassmorphic layouts and Lucide icons.

---

## 📂 Repository Structure

- **`/backend`**: Node.js/Express service responsible for UDP local discovery, WS state synchronization, and custom binary raw TCP file upload/download streams.
- **`/frontend`**: Vite + React client styled with Tailwind CSS v4 featuring drag-and-drop peer sharing, dynamic settings, and file trackers.

---

## ⚡ Quick Start

### 1. Run the Backend Server
```bash
cd backend
npm install
npm run dev # Starts HTTP API (5050), TCP (5051), and UDP (8585)
```

### 2. Run the Frontend Client
```bash
cd frontend
npm install
npm run dev # Starts Vite React dev client on port 3001
```

Open [http://localhost:3001](http://localhost:3001) in your browser. To connect other devices on the same Wi-Fi, load the local network URL displayed in the terminal logs (e.g. `http://<your-ip>:3001`).
