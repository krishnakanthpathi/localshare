# 💻 LocalShare Frontend

Modern dark-mode Web UI for LocalShare built with React 19, Vite, and TailwindCSS.

## 🚀 Quick Start

```bash
# 1. Navigate to frontend
cd localshare/frontend

# 2. Install Node dependencies
npm install

# 3. Start development server
npm run dev
```

The app will start at `http://localhost:5173`.

## ⚙️ Custom Ports & Backend Target

You can configure the Vite dev server port and the target backend API endpoint in `.env`:

```ini
VITE_PORT=5173
VITE_API_BASE_URL=http://localhost:4000
```

To run on a custom port:
```bash
VITE_PORT=3000 npm run dev
```

## 📦 Building for Production

```bash
npm run build
```

This compiles the static assets into `dist/` which can be served by the LocalShare FastAPI backend or any static Web host.
