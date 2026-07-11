import React, { useState } from 'react';
import { useWebSockets } from './hooks/useWebSockets';
import PeerGrid from './components/PeerGrid';
import LocalExplorer from './components/LocalExplorer';
import TransferTracker from './components/TransferTracker';
import HandshakePrompt from './components/HandshakePrompt';
import SettingsDialog from './components/SettingsDialog';
import { Laptop, Settings, Share2, Wifi, WifiOff } from 'lucide-react';
import './App.css';

export default function App() {
  const {
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
    rejectTransfer
  } = useWebSockets();

  const [showSettings, setShowSettings] = useState(false);

  // Core handler for dragging & dropping or browsing files to send to a remote peer
  const handleSendToPeer = async (peer, files) => {
    // 1. Upload the files locally first (since browser can't read path directly)
    const uploadRes = await uploadLocalFile(files);
    if (!uploadRes.success) {
      alert(`Local upload failed: ${uploadRes.error}`);
      return;
    }

    // 2. Trigger the TCP socket send to the peer for each file
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const sendRes = await sendToPeer(peer.ip, peer.port, file.name);
      if (!sendRes.success) {
        alert(`Failed to send "${file.name}": ${sendRes.error}`);
      }
    }
  };

  // Handler for sharing an already uploaded/existing file from the local file explorer
  const handleQuickShare = async (peer, fileName) => {
    const sendRes = await sendToPeer(peer.ip, peer.port, fileName);
    if (!sendRes.success) {
      alert(`Failed to share "${fileName}": ${sendRes.error}`);
    }
  };

  return (
    <div className="min-h-screen bg-background-dark py-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto flex flex-col justify-between">
      {/* Top Header Banner */}
      <header className="w-full flex flex-col md:flex-row md:items-center justify-between p-6 rounded-2xl glass border-white/5 bg-white/5 mb-8 gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-tr from-primary-neon to-secondary-neon rounded-2xl shadow-lg shadow-primary-neon/20">
            <Share2 className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 m-0 p-0 leading-none">
              LocalShare
              <span className="text-[10px] uppercase font-bold tracking-widest text-primary-neon bg-primary-neon/15 px-2 py-0.5 rounded border border-primary-neon/20">
                P2P TCP
              </span>
            </h1>
            <p className="text-xs text-gray-400 mt-1 leading-none">
              High-speed zero-config local file and folder sharing
            </p>
          </div>
        </div>

        {/* Local Node Configuration Info */}
        {localConfig && (
          <div className="flex flex-wrap items-center gap-6 text-sm text-left">
            <div className="flex items-center gap-2.5 bg-white/5 border border-white/5 px-4 py-2 rounded-xl">
              <Laptop className="w-4 h-4 text-secondary-neon" />
              <div>
                <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wide">This Device</div>
                <div className="font-semibold text-white truncate max-w-[140px]">{localConfig.deviceName}</div>
              </div>
            </div>

            <div className="flex items-center gap-2.5 bg-white/5 border border-white/5 px-4 py-2 rounded-xl">
              <Wifi className="w-4 h-4 text-success-neon animate-pulse" />
              <div>
                <div className="text-[10px] text-gray-500 font-bold uppercase tracking-wide">Local IP</div>
                <div className="font-mono text-white text-xs">{localConfig.localIp}</div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowSettings(true)}
                className="p-3 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white rounded-xl transition-all shadow-md cursor-pointer hover:scale-105"
                title="Open Sharing Settings"
              >
                <Settings className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </header>

      {/* Main Grid Dashboard */}
      <main className="flex-grow flex flex-col gap-10">
        {/* Connection Interrupted Warning */}
        {!isWsConnected && (
          <div className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl border border-red-500/20 bg-red-500/10 text-sm font-semibold text-red-400 animate-pulse">
            <WifiOff className="w-4 h-4" />
            Backend connection lost. Trying to reconnect...
          </div>
        )}

        {/* LAN Peers */}
        <section>
          <PeerGrid 
            peers={peers} 
            onSendFile={handleSendToPeer} 
            isWsConnected={isWsConnected} 
          />
        </section>

        {/* Divider line */}
        <div className="h-px bg-gradient-to-r from-transparent via-white/10 to-transparent"></div>

        {/* Local storage files list & drag box */}
        <section className="mb-8">
          <LocalExplorer 
            files={localFiles} 
            peers={peers}
            onUpload={uploadLocalFile} 
            onDelete={deleteLocalFile}
            onSendFile={handleQuickShare}
          />
        </section>
      </main>

      {/* Floating active transfer widgets overlay */}
      <TransferTracker transfers={activeTransfers} />

      {/* Interactive Handshake prompts */}
      {incomingPrompt && (
        <HandshakePrompt
          prompt={incomingPrompt}
          onAccept={acceptTransfer}
          onReject={rejectTransfer}
        />
      )}

      {/* Settings Dialog Modal */}
      {showSettings && localConfig && (
        <SettingsDialog
          currentConfig={localConfig}
          onSave={updateConfig}
          onClose={() => setShowSettings(false)}
        />
      )}

      {/* Footer footer */}
      <footer className="w-full text-center border-t border-white/5 pt-6 mt-12 text-xs text-gray-500 flex justify-between items-center">
        <p>LocalShare Client v1.0.0 &bull; Secure P2P Local Transfer</p>
        <p className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-success-neon"></span>
          All local operations sandboxed
        </p>
      </footer>
    </div>
  );
}
