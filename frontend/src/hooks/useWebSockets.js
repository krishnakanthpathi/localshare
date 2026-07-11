import { useState, useEffect, useRef, useCallback } from 'react';

// Dynamically target the host loading the frontend, allowing other network devices to connect
const API_BASE = `http://${window.location.hostname}:5050/api`;
const WS_BASE = `ws://${window.location.hostname}:5050`;

export const useWebSockets = () => {
  const [peers, setPeers] = useState([]);
  const [localConfig, setLocalConfig] = useState(null);
  const [localFiles, setLocalFiles] = useState([]);
  const [incomingPrompt, setIncomingPrompt] = useState(null);
  const [activeTransfers, setActiveTransfers] = useState({});
  const [isWsConnected, setIsWsConnected] = useState(false);

  const socketRef = useRef(null);

  // Fetch local file explorer items
  const fetchFiles = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/peers/files`);
      const data = await res.json();
      if (data.success) {
        setLocalFiles(data.files);
      }
    } catch (err) {
      console.error('[WebSockets] Failed to fetch files:', err);
    }
  }, []);

  // Fetch backend configurations
  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/system/config`);
      const data = await res.json();
      if (data.success) {
        setLocalConfig(data.config);
      }
    } catch (err) {
      console.error('[WebSockets] Failed to fetch configurations:', err);
    }
  }, []);

  // Refresh discovered LAN peers list
  const fetchPeers = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/peers`);
      const data = await res.json();
      if (data.success) {
        setPeers(data.peers);
      }
    } catch (err) {
      console.error('[WebSockets] Failed to fetch peers:', err);
    }
  }, []);

  // Save configurations dynamically
  const updateConfig = async (newConfig) => {
    try {
      const res = await fetch(`${API_BASE}/system/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      });
      const data = await res.json();
      if (data.success) {
        setLocalConfig(data.config);
        return { success: true };
      }
      return { success: false, error: data.error };
    } catch (err) {
      return { success: false, error: err.message };
    }
  };

  // Upload file from browser to local storage
  const uploadLocalFile = async (files) => {
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }
    try {
      const res = await fetch(`${API_BASE}/peers/files/upload`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.success) {
        fetchFiles();
        return { success: true };
      }
      return { success: false, error: data.error };
    } catch (err) {
      return { success: false, error: err.message };
    }
  };

  // Delete a local file
  const deleteLocalFile = async (fileName) => {
    try {
      const res = await fetch(`${API_BASE}/peers/files/${encodeURIComponent(fileName)}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (data.success) {
        fetchFiles();
        return { success: true };
      }
      return { success: false, error: data.error };
    } catch (err) {
      return { success: false, error: err.message };
    }
  };

  // Trigger TCP send from this device to a remote peer
  const sendToPeer = async (peerIp, peerPort, fileName, filePath = '') => {
    try {
      const res = await fetch(`${API_BASE}/peers/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ peerIp, peerPort, fileName, filePath })
      });
      const data = await res.json();
      if (data.success) {
        return { success: true };
      }
      return { success: false, error: data.error };
    } catch (err) {
      return { success: false, error: err.message };
    }
  };

  // WebSocket handshake accept
  const acceptTransfer = (transferId) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: 'ACCEPT_TRANSFER',
        data: { transferId }
      }));
    }
    setIncomingPrompt(null);
  };

  // WebSocket handshake reject
  const rejectTransfer = (transferId) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: 'REJECT_TRANSFER',
        data: { transferId }
      }));
    }
    setIncomingPrompt(null);
  };

  // WebSocket cancel active transfer
  const cancelTransfer = (transferId) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: 'CANCEL_TRANSFER',
        data: { transferId }
      }));
    }
  };

  useEffect(() => {
    fetchConfig();
    fetchFiles();
    fetchPeers();

    const connectWS = () => {
      console.log('[WS] Connecting to:', WS_BASE);
      const ws = new WebSocket(WS_BASE);

      ws.onopen = () => {
        setIsWsConnected(true);
        console.log('[WS] Connection established.');
      };

      ws.onmessage = (event) => {
        try {
          const { type, data } = JSON.parse(event.data);
          
          switch (type) {
            case 'PEERS_UPDATED':
              setPeers(data);
              break;

            case 'FILES_CHANGED':
              fetchFiles();
              break;

            case 'INCOMING_TRANSFER_PROMPT':
              setIncomingPrompt(data);
              setActiveTransfers(prev => ({
                ...prev,
                [data.transferId]: {
                  transferId: data.transferId,
                  fileName: data.fileName,
                  fileSize: data.fileSize,
                  bytesReceived: 0,
                  status: 'PROMPTED',
                  isFolder: data.isFolder,
                  direction: 'INBOUND'
                }
              }));
              break;

            case 'TRANSFER_PROGRESS':
              setActiveTransfers(prev => {
                const item = prev[data.transferId];
                if (!item) return prev;
                return {
                  ...prev,
                  [data.transferId]: {
                    ...item,
                    bytesReceived: data.bytesReceived,
                    status: 'RECEIVING'
                  }
                };
              });
              break;

            case 'TRANSFER_COMPLETE':
              setActiveTransfers(prev => {
                const item = prev[data.transferId];
                if (!item) return prev;
                return {
                  ...prev,
                  [data.transferId]: {
                    ...item,
                    bytesReceived: item.fileSize,
                    status: 'COMPLETED'
                  }
                };
              });
              setTimeout(() => {
                setActiveTransfers(prev => {
                  const copy = { ...prev };
                  delete copy[data.transferId];
                  return copy;
                });
              }, 5000);
              fetchFiles();
              break;

            case 'TRANSFER_CANCELLED':
              setIncomingPrompt(prev => prev && prev.transferId === data.transferId ? null : prev);
              setActiveTransfers(prev => {
                const item = prev[data.transferId];
                if (!item) return prev;
                return {
                  ...prev,
                  [data.transferId]: {
                    ...item,
                    status: 'CANCELLED'
                  }
                };
              });
              setTimeout(() => {
                setActiveTransfers(prev => {
                  const copy = { ...prev };
                  delete copy[data.transferId];
                  return copy;
                });
              }, 4000);
              break;

            case 'TRANSFER_REJECTED':
              setIncomingPrompt(prev => prev && prev.transferId === data.transferId ? null : prev);
              setActiveTransfers(prev => {
                const copy = { ...prev };
                delete copy[data.transferId];
                return copy;
              });
              break;

            case 'TRANSFER_ERROR':
              setActiveTransfers(prev => {
                const item = prev[data.transferId];
                if (!item) return prev;
                return {
                  ...prev,
                  [data.transferId]: {
                    ...item,
                    status: 'FAILED',
                    error: data.error
                  }
                };
              });
              setTimeout(() => {
                setActiveTransfers(prev => {
                  const copy = { ...prev };
                  delete copy[data.transferId];
                  return copy;
                });
              }, 6000);
              break;

            case 'SEND_STARTED':
              setActiveTransfers(prev => ({
                ...prev,
                [data.transferId]: {
                  transferId: data.transferId,
                  fileName: data.fileName,
                  fileSize: data.fileSize || 0,
                  bytesReceived: 0,
                  status: 'SENDING',
                  direction: 'OUTBOUND'
                }
              }));
              break;

            case 'SEND_PROGRESS':
              setActiveTransfers(prev => {
                const item = prev[data.transferId];
                if (!item) return prev;
                return {
                  ...prev,
                  [data.transferId]: {
                    ...item,
                    bytesReceived: data.bytesSent,
                    fileSize: data.fileSize || item.fileSize
                  }
                };
              });
              break;

            case 'SEND_COMPLETE':
              setActiveTransfers(prev => {
                const item = prev[data.transferId];
                if (!item) return prev;
                return {
                  ...prev,
                  [data.transferId]: {
                    ...item,
                    status: 'COMPLETED'
                  }
                };
              });
              setTimeout(() => {
                setActiveTransfers(prev => {
                  const copy = { ...prev };
                  delete copy[data.transferId];
                  return copy;
                });
              }, 5000);
              break;

            case 'SEND_REJECTED':
              setActiveTransfers(prev => {
                const item = prev[data.transferId];
                if (!item) return prev;
                return {
                  ...prev,
                  [data.transferId]: {
                    ...item,
                    status: 'REJECTED'
                  }
                };
              });
              setTimeout(() => {
                setActiveTransfers(prev => {
                  const copy = { ...prev };
                  delete copy[data.transferId];
                  return copy;
                });
              }, 5000);
              break;

            case 'SEND_CANCELLED':
              setActiveTransfers(prev => {
                const item = prev[data.transferId];
                if (!item) return prev;
                return {
                  ...prev,
                  [data.transferId]: {
                    ...item,
                    status: 'CANCELLED'
                  }
                };
              });
              setTimeout(() => {
                setActiveTransfers(prev => {
                  const copy = { ...prev };
                  delete copy[data.transferId];
                  return copy;
                });
              }, 4000);
              break;

            default:
              console.log('[WS] Unhandled WebSocket event type:', type);
          }
        } catch (err) {
          console.error('[WS] Failed to parse socket message:', err);
        }
      };

      ws.onclose = () => {
        setIsWsConnected(false);
        console.log('[WS] Disconnected. Attempting reconnection in 3s...');
        socketRef.current = null;
        setTimeout(connectWS, 3000);
      };

      ws.onerror = (err) => {
        console.error('[WS] Socket error occurred:', err);
        ws.close();
      };

      socketRef.current = ws;
    };

    connectWS();

    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [fetchFiles, fetchPeers, fetchConfig]);

  return {
    peers,
    localConfig,
    localFiles,
    incomingPrompt,
    activeTransfers,
    isWsConnected,
    updateConfig,
    uploadLocalFile,
    deleteLocalFile,
    sendToPeer,
    acceptTransfer,
    rejectTransfer,
    cancelTransfer,
    refreshFiles: fetchFiles
  };
};
