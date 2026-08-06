import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Wifi,
  UploadCloud,
  FileText,
  Share2,
  Copy,
  QrCode,
  ShieldAlert,
  CheckCircle2,
  Download,
  RefreshCw,
  FolderPlus,
  File,
  HardDrive,
  Check,
  X,
  Settings,
  Zap,
  Trash2,
  StopCircle,
  Power,
  Folder,
  ChevronDown,
  ChevronRight
} from 'lucide-react';

export default function App() {
  const [config, setConfig] = useState({
    device_name: 'Loading...',
    primary_ip: '127.0.0.1',
    auto_approve: true,
    upload_dir: '~'
  });
  const [peers, setPeers] = useState([]);
  const [transfers, setTransfers] = useState([]);
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [clipboardText, setClipboardText] = useState('');
  const [copiedToast, setCopiedToast] = useState(false);
  const [showQRModal, setShowQRModal] = useState(false);
  const [qrSVG, setQrSVG] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [selectedPeer, setSelectedPeer] = useState(null);
  const [expandedFolders, setExpandedFolders] = useState({});

  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);
  const activeXhrs = useRef({});

  // Poll data periodically
  useEffect(() => {
    fetchConfig();
    fetchPeers();
    fetchTransfers();
    fetchClipboard();
    fetchPending();

    const interval = setInterval(() => {
      fetchPeers();
      fetchTransfers();
      fetchPending();
    }, 2500);

    return () => clearInterval(interval);
  }, []);

  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      setConfig(data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchPeers = async () => {
    try {
      const res = await fetch('/api/peers');
      const data = await res.json();
      setPeers(data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchTransfers = async () => {
    try {
      const res = await fetch('/api/transfers');
      const backendData = await res.json();
      setTransfers((prev) => {
        const activeUploading = prev.filter((t) => t.status === 'UPLOADING');
        const merged = [...backendData];
        for (let item of activeUploading) {
          const idx = merged.findIndex((b) => b.id === item.id);
          if (idx !== -1) {
            merged[idx] = { ...merged[idx], received_bytes: item.received_bytes, speed: item.speed };
          } else {
            merged.unshift(item);
          }
        }
        return merged;
      });
    } catch (e) {
      console.error(e);
    }
  };

  const fetchClipboard = async () => {
    try {
      const res = await fetch('/api/clipboard');
      const data = await res.json();
      if (data.current) setClipboardText(data.current);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchPending = async () => {
    try {
      const res = await fetch('/api/pending');
      const data = await res.json();
      setPendingApprovals(data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchQR = async () => {
    try {
      const res = await fetch('/api/qrcode');
      const svg = await res.text();
      setQrSVG(svg);
      setShowQRModal(true);
    } catch (e) {
      console.error(e);
    }
  };

  const stopTransfer = async (transferId) => {
    if (activeXhrs.current[transferId]) {
      try {
        activeXhrs.current[transferId].abort();
      } catch (e) {}
      delete activeXhrs.current[transferId];
    }
    try {
      await fetch('/api/transfers/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transfer_id: transferId })
      });
    } catch (e) {
      console.error(e);
    }
    setTransfers((prev) =>
      prev.map((t) => (t.id === transferId ? { ...t, status: 'CANCELLED', speed: 0 } : t))
    );
  };

  const stopFolderBatch = (items) => {
    items.forEach((item) => stopTransfer(item.id));
  };

  const shutdownNode = async () => {
    if (window.confirm('Are you sure you want to stop and shutdown the LocalShare node process?')) {
      try {
        await fetch('/api/shutdown', { method: 'POST' });
        alert('LocalShare node process has stopped.');
      } catch (e) {
        alert('LocalShare node process has stopped.');
      }
    }
  };

  const toggleExpandFolder = (key) => {
    setExpandedFolders((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const scanDropItems = async (dataTransfer) => {
    const items = dataTransfer.items;
    const fileEntries = [];

    const processEntry = async (entry, path = '') => {
      if (entry.isFile) {
        await new Promise((resolve) => {
          entry.file((f) => {
            f.relativePath = path ? `${path}/${f.name}` : f.name;
            fileEntries.push(f);
            resolve();
          });
        });
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        const entries = await new Promise((resolve) => reader.readEntries(resolve));
        for (let child of entries) {
          await processEntry(child, path ? `${path}/${entry.name}` : entry.name);
        }
      }
    };

    if (items) {
      for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry ? items[i].webkitGetAsEntry() : null;
        if (entry) {
          await processEntry(entry);
        } else if (items[i].kind === 'file') {
          fileEntries.push(items[i].getAsFile());
        }
      }
    } else {
      return Array.from(dataTransfer.files);
    }
    return fileEntries;
  };

  const uploadFileList = (fileList) => {
    if (!fileList || fileList.length === 0) return;

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      const relPath = file.relativePath || file.webkitRelativePath || file.name;
      const tempId = `up_${Date.now()}_${i}_${Math.random().toString(36).substr(2, 4)}`;

      const formData = new FormData();
      formData.append('file', file, relPath);
      formData.append('transfer_id', tempId);
      formData.append('rel_path', relPath);

      const newTransfer = {
        id: tempId,
        filename: file.name,
        rel_path: relPath,
        total_bytes: file.size,
        received_bytes: 0,
        sender_ip: 'Local Browser',
        status: 'UPLOADING',
        start_time: Date.now() / 1000,
        speed: 0
      };

      setTransfers((prev) => [newTransfer, ...prev]);

      const xhr = new XMLHttpRequest();
      activeXhrs.current[tempId] = xhr;
      const startT = Date.now();

      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable) {
          const loaded = evt.loaded;
          const total = evt.total;
          const elapsed = Math.max((Date.now() - startT) / 1000, 0.001);
          const speed = loaded / elapsed;

          setTransfers((prev) =>
            prev.map((t) =>
              t.id === tempId
                ? { ...t, received_bytes: loaded, total_bytes: total, speed }
                : t
            )
          );
        }
      };

      xhr.onload = () => {
        delete activeXhrs.current[tempId];
        setTransfers((prev) =>
          prev.map((t) =>
            t.id === tempId
              ? { ...t, status: 'COMPLETED', received_bytes: file.size }
              : t
          )
        );
        fetchTransfers();
      };

      xhr.onerror = () => {
        delete activeXhrs.current[tempId];
        setTransfers((prev) =>
          prev.map((t) => (t.id === tempId ? { ...t, status: 'FAILED' } : t))
        );
      };

      xhr.onabort = () => {
        delete activeXhrs.current[tempId];
      };

      xhr.open('POST', '/api/upload', true);
      xhr.send(formData);
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = await scanDropItems(e.dataTransfer);
    uploadFileList(files);
  };

  const syncClipboard = async (broadcast) => {
    if (!clipboardText) return;
    try {
      await fetch('/api/clipboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: clipboardText, broadcast })
      });
      setCopiedToast(true);
      setTimeout(() => setCopiedToast(false), 2000);
    } catch (e) {
      console.error(e);
    }
  };

  const toggleAutoApprove = async () => {
    const newVal = !config.auto_approve;
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_approve: newVal })
      });
      setConfig({ ...config, auto_approve: newVal });
    } catch (e) {
      console.error(e);
    }
  };

  const respondApproval = async (transferId, action) => {
    try {
      await fetch('/api/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transfer_id: transferId, action })
      });
      fetchPending();
      fetchTransfers();
    } catch (e) {
      console.error(e);
    }
  };

  const formatBytes = (bytes) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Group transfer items by root folder or individual file
  const groupTransfers = (items) => {
    const groups = {};
    for (let t of items) {
      const parts = (t.rel_path || t.filename || '').split('/');
      const isFolder = parts.length > 1;
      const rootKey = isFolder ? parts[0] : t.id;

      if (!groups[rootKey]) {
        groups[rootKey] = {
          key: rootKey,
          isFolder: isFolder,
          folderName: parts[0],
          items: [],
          totalBytes: 0,
          receivedBytes: 0,
          speed: 0,
          hasUploading: false,
          hasCancelled: false,
          allCompleted: true
        };
      }

      const g = groups[rootKey];
      g.items.push(t);
      g.totalBytes += t.total_bytes || 0;
      g.receivedBytes += t.received_bytes || 0;
      g.speed += t.speed || 0;
      if (t.status === 'UPLOADING' || t.status === 'IN_PROGRESS') g.hasUploading = true;
      if (t.status === 'CANCELLED' || t.status === 'FAILED') g.hasCancelled = true;
      if (t.status !== 'COMPLETED') g.allCompleted = false;
    }
    return Object.values(groups);
  };

  const groupedTransfers = groupTransfers(transfers);

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100 flex flex-col font-sans selection:bg-white selection:text-black">
      {/* Header Bar */}
      <header className="sticky top-0 z-50 bg-[#09090b]/85 backdrop-blur-xl border-b border-zinc-800/80">
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <motion.div
              whileHover={{ scale: 1.05 }}
              className="w-9 h-9 rounded-xl bg-white text-black flex items-center justify-center font-bold shadow-md shadow-white/5"
            >
              <Zap className="w-5 h-5 fill-current text-black" />
            </motion.div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-bold tracking-tight text-white font-mono">
                  LocalShare
                </h1>
                <span className="shadcn-badge-mono text-[10px] px-2 py-0.5 font-mono">v1.0 Mesh</span>
              </div>
              <p className="text-[11px] text-zinc-400 font-mono mt-0.5">
                {config.device_name} • <span className="text-zinc-200">{config.primary_ip}</span>
              </p>
            </div>
          </div>

          {/* Right Action Controls */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-950 border border-zinc-800 text-zinc-300 text-xs font-mono">
              <span className="w-2 h-2 rounded-full bg-white animate-pulse"></span>
              <span>{peers.length} Peers Active</span>
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={fetchQR}
              className="shadcn-button-primary px-3.5 py-2 text-xs flex items-center gap-2 shadow-sm"
            >
              <QrCode className="w-4 h-4 text-black" />
              <span>Connect Mobile</span>
            </motion.button>
          </div>
        </div>
      </header>

      {/* Main Grid Content */}
      <main className="max-w-7xl mx-auto w-full p-6 grid grid-cols-1 lg:grid-cols-3 gap-6 relative z-10 flex-1">
        
        {/* Left Column (2 Cols wide on desktop) */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Upload Drop Zone Card */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            className="shadcn-card p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-sm font-semibold flex items-center gap-2 text-white">
                  <UploadCloud className="w-4 h-4 text-white" /> Share Files & Folders
                </h2>
                <p className="text-xs text-zinc-400 mt-0.5">Drag & Drop files or directory trees across LAN</p>
              </div>
              <span className="shadcn-badge-mono px-2.5 py-1">P2P Mesh</span>
            </div>

            <motion.div
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              whileHover={{ scale: 1.002 }}
              className={`border-2 border-dashed rounded-xl p-8 text-center transition-all flex flex-col items-center justify-center gap-3 ${
                isDragging
                  ? 'border-white bg-zinc-900'
                  : 'border-zinc-800 bg-zinc-950/60 hover:border-zinc-600 hover:bg-zinc-900/40'
              }`}
            >
              <div className="w-12 h-12 rounded-xl bg-zinc-900 border border-zinc-800 text-white flex items-center justify-center text-xl shadow-inner">
                ⚡
              </div>
              <div>
                <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">Drag & Drop Files or Folders Here</h3>
                <p className="text-[11px] text-zinc-500 mt-1">Preserves directory hierarchy and relative paths</p>
              </div>

              <div className="flex items-center gap-3 mt-2">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="shadcn-button-outline px-4 py-2 text-xs flex items-center gap-2"
                >
                  <File className="w-3.5 h-3.5" /> Select Files
                </button>

                <button
                  onClick={() => folderInputRef.current?.click()}
                  className="shadcn-button-outline px-4 py-2 text-xs flex items-center gap-2"
                >
                  <FolderPlus className="w-3.5 h-3.5" /> Select Folder
                </button>
              </div>

              {/* Hidden file input */}
              <input
                type="file"
                ref={fileInputRef}
                multiple
                className="hidden"
                onChange={(e) => uploadFileList(e.target.files)}
              />

              {/* Hidden folder input */}
              <input
                type="file"
                ref={folderInputRef}
                webkitdirectory=""
                directory=""
                multiple
                className="hidden"
                onChange={(e) => uploadFileList(e.target.files)}
              />
            </motion.div>
          </motion.div>

          {/* Discovered Mesh Devices Card */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            className="shadcn-card p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold flex items-center gap-2 text-white">
                <Wifi className="w-4 h-4 text-white" /> Discovered Mesh Devices ({peers.length})
              </h2>
              <button
                onClick={fetchPeers}
                className="p-1.5 rounded-lg bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 text-zinc-300 transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>

            {peers.length === 0 ? (
              <div className="p-6 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-950/40">
                <p className="text-xs text-zinc-500 font-mono">Scanning LAN on UDP 41234... Make sure LocalShare is running on target device.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {peers.map((peer, idx) => (
                  <motion.div
                    key={peer.ip}
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: idx * 0.04 }}
                    whileHover={{ scale: 1.02 }}
                    onClick={() => setSelectedPeer(peer)}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-center gap-3 ${
                      selectedPeer?.ip === peer.ip
                        ? 'border-white bg-zinc-900'
                        : 'border-zinc-800 bg-zinc-950/60 hover:border-zinc-700'
                    }`}
                  >
                    <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 text-white flex items-center justify-center font-bold text-xs">
                      {peer.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="overflow-hidden">
                      <p className="text-xs font-semibold text-zinc-200 truncate">{peer.name}</p>
                      <p className="text-[10px] text-zinc-400 font-mono truncate">{peer.ip} • {peer.latency}ms</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>

          {/* Transfers Log Card with Folder & Subfolder Batch Progress */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="shadcn-card p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold flex items-center gap-2 text-white">
                <HardDrive className="w-4 h-4 text-white" /> Transfers & Subfolder Batch Progress
              </h2>
              <span className="text-[11px] text-zinc-500 font-mono">{groupedTransfers.length} Batches</span>
            </div>

            {groupedTransfers.length === 0 ? (
              <p className="text-xs text-zinc-500 font-mono">No active or recent transfers.</p>
            ) : (
              <div className="space-y-4">
                {groupedTransfers.slice(0, 10).map((group) => {
                  const pct = Math.min(
                    Math.round((group.receivedBytes / (group.totalBytes || 1)) * 100),
                    100
                  );
                  const isComplete = group.allCompleted;
                  const isUploading = group.hasUploading;
                  const isCancelled = group.hasCancelled && !isUploading;
                  const speedMb = group.speed ? (group.speed / (1024 * 1024)).toFixed(2) : '0';
                  const isExpanded = !!expandedFolders[group.key];

                  return (
                    <div
                      key={group.key}
                      className="p-4 rounded-xl border border-zinc-800 bg-zinc-950/80 transition-all space-y-3"
                    >
                      {/* Folder Batch Header */}
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          {group.isFolder ? (
                            <button
                              onClick={() => toggleExpandFolder(group.key)}
                              className="p-1 rounded bg-zinc-900 border border-zinc-800 text-white hover:bg-zinc-800 transition-colors"
                            >
                              {isExpanded ? (
                                <ChevronDown className="w-4 h-4" />
                              ) : (
                                <ChevronRight className="w-4 h-4" />
                              )}
                            </button>
                          ) : (
                            <div className="w-6 h-6 rounded bg-zinc-900 border border-zinc-800 flex items-center justify-center">
                              <File className="w-3.5 h-3.5 text-zinc-300" />
                            </div>
                          )}

                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              {group.isFolder && <Folder className="w-4 h-4 text-white shrink-0" />}
                              <span className="font-semibold text-zinc-100 truncate font-mono text-xs">
                                {group.isFolder ? `${group.folderName}/` : group.items[0]?.rel_path || group.items[0]?.filename}
                              </span>
                              {group.isFolder && (
                                <span className="shadcn-badge-mono text-[10px] px-2 py-0.2">
                                  {group.items.length} files
                                </span>
                              )}
                            </div>
                            <p className="text-[10px] text-zinc-400 font-mono mt-0.5">
                              {formatBytes(group.receivedBytes)} / {formatBytes(group.totalBytes)} •{' '}
                              <span
                                className={
                                  isComplete
                                    ? 'text-white font-semibold'
                                    : isCancelled
                                    ? 'text-zinc-500 line-through'
                                    : 'text-zinc-300'
                                }
                              >
                                {isUploading ? 'UPLOADING' : isComplete ? 'COMPLETED' : isCancelled ? 'CANCELLED' : 'IN_PROGRESS'}
                              </span>
                              {isUploading && speedMb > 0 && ` • ${speedMb} MB/s`}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-xs font-mono font-bold text-zinc-300">{pct}%</span>
                          {isUploading && (
                            <button
                              onClick={() => stopFolderBatch(group.items)}
                              className="px-2.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-700 hover:bg-zinc-800 text-zinc-200 text-xs font-semibold transition-colors flex items-center gap-1"
                            >
                              <StopCircle className="w-3.5 h-3.5 text-white" /> Stop
                            </button>
                          )}
                          {isComplete && group.isFolder && (
                            <a
                              href={`/api/download/${encodeURIComponent(group.folderName)}`}
                              download
                              className="shadcn-button-primary px-3 py-1.5 text-xs flex items-center gap-1.5"
                            >
                              <Download className="w-3.5 h-3.5 text-black" /> Download Folder (.zip)
                            </a>
                          )}
                          {isComplete && !group.isFolder && (
                            <a
                              href={`/api/download/${encodeURIComponent(group.items[0]?.rel_path || group.items[0]?.filename)}`}
                              download
                              className="shadcn-button-outline px-3 py-1.5 text-xs flex items-center gap-1.5"
                            >
                              <Download className="w-3.5 h-3.5" /> Download
                            </a>
                          )}
                        </div>
                      </div>

                      {/* Overall Group Progress Bar */}
                      <div className="w-full h-1.5 bg-zinc-900 rounded-full overflow-hidden border border-zinc-800">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 0.15 }}
                          className={`h-full ${isCancelled ? 'bg-zinc-600' : 'bg-white'} rounded-full`}
                        />
                      </div>

                      {/* Collapsible Subfolder Tree & Individual File Progress Bars */}
                      <AnimatePresence>
                        {group.isFolder && isExpanded && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="pt-2 pl-4 border-l border-zinc-800 space-y-2 mt-2"
                          >
                            <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-mono font-semibold mb-1">
                              Subfolder & File Details ({group.items.length} items):
                            </p>
                            {group.items.map((item) => {
                              const itemPct = Math.min(
                                Math.round((item.received_bytes / (item.total_bytes || 1)) * 100),
                                100
                              );
                              const subPath = item.rel_path || item.filename;
                              return (
                                <div
                                  key={item.id}
                                  className="p-2 rounded-lg bg-zinc-900/90 border border-zinc-800/80 flex items-center justify-between text-xs font-mono"
                                >
                                  <div className="min-w-0 flex-1 pr-3">
                                    <div className="flex items-center justify-between text-[11px] mb-0.5">
                                      <span className="text-zinc-300 truncate font-mono">
                                        📄 {subPath}
                                      </span>
                                      <span className="text-zinc-400 text-[10px]">{itemPct}%</span>
                                    </div>
                                    <div className="w-full h-1 bg-zinc-800 rounded-full overflow-hidden">
                                      <div
                                        style={{ width: `${itemPct}%` }}
                                        className="h-full bg-zinc-300 rounded-full"
                                      />
                                    </div>
                                  </div>
                                  <span className="text-[10px] text-zinc-500 shrink-0">
                                    {formatBytes(item.received_bytes)} / {formatBytes(item.total_bytes)}
                                  </span>
                                </div>
                              );
                            })}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  );
                })}
              </div>
            )}
          </motion.div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">

          {/* Pending Transfer Approval Modal/Card */}
          <AnimatePresence>
            {pendingApprovals.length > 0 && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="shadcn-card p-6 border-zinc-500 bg-zinc-900/90"
              >
                <div className="flex items-center gap-2 text-white font-semibold text-xs mb-3">
                  <ShieldAlert className="w-4 h-4 text-white" /> Incoming Transfer Approval
                </div>
                <div className="text-xs text-zinc-300 space-y-1 mb-4">
                  <p>File: <strong className="text-white">{pendingApprovals[0].filename}</strong> ({formatBytes(pendingApprovals[0].filesize)})</p>
                  <p>Sender IP: <span className="font-mono text-zinc-400">{pendingApprovals[0].sender_ip}</span></p>
                  {pendingApprovals[0].suspicious && (
                    <p className="text-zinc-300 font-medium">⚠️ Executable extension detected!</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => respondApproval(pendingApprovals[0].transfer_id, 'ACCEPT')}
                    className="flex-1 py-2 rounded-lg bg-white text-black font-semibold text-xs hover:bg-zinc-200 transition-colors flex items-center justify-center gap-1"
                  >
                    <Check className="w-3.5 h-3.5" /> Accept
                  </button>
                  <button
                    onClick={() => respondApproval(pendingApprovals[0].transfer_id, 'REJECT')}
                    className="flex-1 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-semibold text-xs transition-colors flex items-center justify-center gap-1"
                  >
                    <X className="w-3.5 h-3.5" /> Decline
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Clipboard & Text Sync Card */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12 }}
            className="shadcn-card p-6"
          >
            <h2 className="text-sm font-semibold flex items-center gap-2 text-white mb-4">
              <FileText className="w-4 h-4 text-white" /> Clipboard & Text Sync
            </h2>

            <div className="space-y-3">
              <textarea
                value={clipboardText}
                onChange={(e) => setClipboardText(e.target.value)}
                placeholder="Type or paste code snippet or text here..."
                className="w-full h-28 p-3 bg-zinc-950 border border-zinc-800 rounded-xl text-xs text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-zinc-500 resize-none font-mono"
              />

              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => syncClipboard(false)}
                  className="shadcn-button-outline py-2 text-xs flex items-center justify-center gap-1.5"
                >
                  <Copy className="w-3.5 h-3.5" /> Copy Local
                </button>
                <button
                  onClick={() => syncClipboard(true)}
                  className="shadcn-button-primary py-2 text-xs flex items-center justify-center gap-1.5"
                >
                  <Share2 className="w-3.5 h-3.5" /> Broadcast
                </button>
              </div>

              {copiedToast && (
                <motion.p
                  initial={{ opacity: 0, y: 3 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="text-xs text-zinc-300 font-mono flex items-center gap-1 justify-center"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-white" /> Synced to clipboard!
                </motion.p>
              )}
            </div>
          </motion.div>

          {/* Preferences Card */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="shadcn-card p-6 space-y-4"
          >
            <h2 className="text-sm font-semibold flex items-center gap-2 text-white">
              <Settings className="w-4 h-4 text-white" /> Preferences & Node Control
            </h2>

            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-300">Auto-Approve Transfers</span>
              <button
                onClick={toggleAutoApprove}
                className={`w-11 h-6 rounded-full transition-colors relative p-1 ${
                  config.auto_approve ? 'bg-white' : 'bg-zinc-800'
                }`}
              >
                <div
                  className={`w-4 h-4 rounded-full transition-transform ${
                    config.auto_approve ? 'translate-x-5 bg-black' : 'translate-x-0 bg-zinc-400'
                  }`}
                />
              </button>
            </div>

            <div className="text-xs space-y-1">
              <span className="text-zinc-400">Target Upload Directory:</span>
              <p className="p-2 rounded-lg bg-zinc-950 text-zinc-300 font-mono text-[10px] break-all border border-zinc-800">
                {config.upload_dir}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-2 pt-2">
              <button
                onClick={async () => {
                  try {
                    await fetch('/api/clear_memory', { method: 'POST' });
                    setTransfers([]);
                    alert('In-memory transfer log cleared and RAM freed!');
                  } catch (e) {
                    console.error(e);
                  }
                }}
                className="w-full py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-400 border border-zinc-800 hover:text-white text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
              >
                <Trash2 className="w-3.5 h-3.5" /> Purge Memory Log & RAM
              </button>

              <button
                onClick={shutdownNode}
                className="w-full py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border border-zinc-700 hover:border-zinc-500 text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
              >
                <Power className="w-3.5 h-3.5 text-white" /> Stop Server Process
              </button>
            </div>
          </motion.div>
        </div>
      </main>

      {/* QR Code Modal */}
      <AnimatePresence>
        {showQRModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowQRModal(false)}
            className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.94, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.94, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="shadcn-card p-6 max-w-sm w-full text-center space-y-4 border border-zinc-700 bg-black"
            >
              <h3 className="text-sm font-bold text-white">📱 Connect Mobile Device</h3>
              <p className="text-xs text-zinc-400">Scan QR code with your phone camera to open Zero-Install web client instantly.</p>
              
              <div
                className="p-4 bg-zinc-950 rounded-xl border border-zinc-800 flex justify-center"
                dangerouslySetInnerHTML={{ __html: qrSVG }}
              />

              <p className="text-xs font-mono text-zinc-200">{`http://${config.primary_ip}:4000`}</p>

              <button
                onClick={() => setShowQRModal(false)}
                className="shadcn-button-outline w-full py-2 text-xs"
              >
                Close
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
