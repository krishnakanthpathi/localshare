import React, { useRef, useState } from 'react';
import { Smartphone, Laptop, Monitor, RefreshCw, Send, Radio } from 'lucide-react';

const getOSIcon = (osType) => {
  if (!osType) return <Laptop className="w-6 h-6" />;
  const os = osType.toLowerCase();
  if (os === 'darwin') return <Laptop className="w-6 h-6 text-blue-400" />;
  if (os === 'win32' || os.includes('win')) return <Monitor className="w-6 h-6 text-sky-400" />;
  if (os === 'linux') return <Monitor className="w-6 h-6 text-orange-400" />;
  return <Smartphone className="w-6 h-6 text-green-400" />;
};

const getOSName = (osType) => {
  if (!osType) return 'Device';
  const os = osType.toLowerCase();
  if (os === 'darwin') return 'macOS';
  if (os === 'win32' || os.includes('win')) return 'Windows';
  if (os === 'linux') return 'Linux';
  return 'Mobile';
};

export default function PeerGrid({ peers, onSendFile, isWsConnected, onAddManualPeer }) {
  const [draggingPeerId, setDraggingPeerId] = useState(null);
  const [sendingPeerId, setSendingPeerId] = useState(null);
  const [newPeerIp, setNewPeerIp] = useState('');
  const fileInputRefs = useRef({});

  const handleAddSubmit = (e) => {
    e.preventDefault();
    if (newPeerIp && newPeerIp.trim()) {
      onAddManualPeer(newPeerIp.trim());
      setNewPeerIp('');
    }
  };

  const handleDragOver = (e, peerId) => {
    e.preventDefault();
    setDraggingPeerId(peerId);
  };

  const handleDragLeave = () => {
    setDraggingPeerId(null);
  };

  const handleDrop = async (e, peer) => {
    e.preventDefault();
    setDraggingPeerId(null);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      setSendingPeerId(peer.id);
      await onSendFile(peer, files);
      setSendingPeerId(null);
    }
  };

  const handleFileSelect = async (e, peer) => {
    const files = e.target.files;
    if (files.length > 0) {
      setSendingPeerId(peer.id);
      await onSendFile(peer, files);
      setSendingPeerId(null);
      e.target.value = ''; // Reset input selection
    }
  };

  const triggerFileInput = (peerId) => {
    if (fileInputRefs.current[peerId]) {
      fileInputRefs.current[peerId].click();
    }
  };

  return (
    <div className="w-full">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <h2 className="text-xl font-semibold text-white flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isWsConnected ? 'bg-primary-neon' : 'bg-red-500'}`}></span>
            <span className={`relative inline-flex rounded-full h-3 w-3 ${isWsConnected ? 'bg-primary-neon' : 'bg-red-500'}`}></span>
          </span>
          Local Network Radar
        </h2>
        
        <div className="flex flex-wrap items-center gap-4 w-full md:w-auto">
          {/* Add Manual Peer Form */}
          <form onSubmit={handleAddSubmit} className="flex items-center gap-2 flex-grow sm:flex-grow-0">
            <input
              type="text"
              value={newPeerIp}
              onChange={(e) => setNewPeerIp(e.target.value)}
              placeholder="Add Tailscale / Remote IP..."
              className="bg-white/5 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-primary-neon w-full sm:w-48 transition-all"
            />
            <button
              type="submit"
              className="bg-primary-neon hover:opacity-90 text-white rounded-xl px-4 py-2 text-xs font-bold transition-all cursor-pointer whitespace-nowrap"
            >
              Add Peer
            </button>
          </form>
          
          <span className="text-sm text-gray-400 hidden sm:inline">
            {peers.length === 1 ? '1 active peer' : `${peers.length} active peers`}
          </span>
        </div>
      </div>

      {peers.length === 0 ? (
        <div className="w-full flex flex-col items-center justify-center p-12 glass rounded-2xl border-white/5 bg-white/5 text-center">
          <div className="relative mb-6">
            <div className="w-20 h-20 rounded-full border border-primary-neon/20 flex items-center justify-center radar-pulse bg-primary-neon/5">
              <Radio className="w-8 h-8 text-primary-neon" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">Scanning local network...</h3>
          <p className="text-sm text-gray-400 max-w-sm">
            Launch LocalShare on other devices (Mac, Windows, Linux, or Mobile) in the same Wi-Fi network to automatically discover them.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
          {peers.map((peer) => (
            <div
              key={peer.id}
              onDragOver={(e) => handleDragOver(e, peer.id)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, peer)}
              onClick={() => triggerFileInput(peer.id)}
              className={`relative cursor-pointer overflow-hidden p-6 rounded-2xl glass border transition-all duration-300 flex flex-col items-center text-center select-none ${
                draggingPeerId === peer.id
                  ? 'border-primary-neon bg-primary-neon/10 scale-105 shadow-lg shadow-primary-neon/20'
                  : 'border-white/10 hover:border-white/20 hover:bg-white/5 hover:-translate-y-1'
              }`}
            >
              {/* Invisible input file for clicks */}
              <input
                type="file"
                multiple
                ref={(el) => (fileInputRefs.current[peer.id] = el)}
                onChange={(e) => handleFileSelect(e, peer)}
                className="hidden"
              />

              {/* OS Badge */}
              <div className="absolute top-4 right-4 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-white/5 border border-white/5 text-gray-400">
                {getOSName(peer.os)}
              </div>

              {/* Device Icon */}
              <div className="p-4 rounded-2xl bg-white/5 border border-white/5 text-white mb-4 mt-2">
                {getOSIcon(peer.os)}
              </div>

              {/* Device Metadata */}
              <h3 className="font-bold text-white mb-1 text-lg truncate max-w-full px-2" title={peer.name}>
                {peer.name}
              </h3>
              <p className="text-sm text-gray-400 mb-4">{peer.ip}</p>

              {/* Drag indicator / Action Button */}
              <div className="w-full mt-auto">
                {sendingPeerId === peer.id ? (
                  <div className="flex items-center justify-center gap-2 text-primary-neon text-sm font-semibold py-2">
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Sending...
                  </div>
                ) : (
                  <button className="w-full flex items-center justify-center gap-2 bg-white/5 hover:bg-primary-neon hover:text-white border border-white/10 hover:border-transparent py-2.5 px-4 rounded-xl text-gray-300 hover:shadow-lg text-sm font-medium transition-all cursor-pointer">
                    <Send className="w-4 h-4" />
                    Drop or Click to Share
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
