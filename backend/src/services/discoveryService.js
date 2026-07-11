import dgram from 'dgram';
import config from '../config/config.js';
import websocketService from './websocketService.js';

class DiscoveryService {
  constructor() {
    this.socket = null;
    this.peers = new Map(); // id -> peer details
    this.broadcastInterval = null;
    this.cleanupInterval = null;
    // Generate a unique device identifier for this run
    this.deviceId = `device_${Math.random().toString(36).substring(2, 10)}`;
  }

  start() {
    const port = config.udpPort;
    this.socket = dgram.createSocket({ type: 'udp4', reuseAddr: true });

    this.socket.on('message', (msg, rinfo) => {
      try {
        const data = JSON.parse(msg.toString());
        
        // Skip announcements from ourselves
        if (data.deviceId === this.deviceId) return;

        const peerId = data.deviceId;
        const now = Date.now();
        const isNew = !this.peers.has(peerId);
        
        this.peers.set(peerId, {
          id: peerId,
          name: data.deviceName,
          ip: rinfo.address, // Always use actual socket sender IP in case of IP change
          port: data.tcpPort,
          os: data.os,
          lastSeen: now
        });

        if (isNew) {
          console.log(`[Discovery] New peer found: ${data.deviceName} at ${rinfo.address}:${data.tcpPort}`);
          this.notifyPeersChanged();
        } else {
          // If IP or Port changed for some reason, notify
          const existing = this.peers.get(peerId);
          if (existing.ip !== rinfo.address || existing.port !== data.tcpPort || existing.name !== data.deviceName) {
            existing.ip = rinfo.address;
            existing.port = data.tcpPort;
            existing.name = data.deviceName;
            this.notifyPeersChanged();
          }
        }
      } catch (err) {
        // Silently discard malformed packets
      }
    });

    this.socket.on('error', (err) => {
      console.error('[Discovery] UDP Socket error:', err.message);
      // Gracefully attempt fallback or just keep running
    });

    this.socket.on('listening', () => {
      try {
        this.socket.setBroadcast(true);
        console.log(`[Discovery] UDP Broadcast listening on port ${port}`);

        // Broadcast presence every 5 seconds
        this.broadcastInterval = setInterval(() => {
          this.broadcastPresence();
        }, 5000);

        // Scan for inactive peers every 5 seconds
        this.cleanupInterval = setInterval(() => {
          this.cleanupStalePeers();
        }, 5000);
      } catch (err) {
        console.error('[Discovery] Failed setting up broadcast socket options:', err);
      }
    });

    try {
      this.socket.bind(port);
    } catch (err) {
      console.error(`[Discovery] Failed binding UDP port ${port}:`, err.message);
    }
  }

  broadcastPresence() {
    if (!this.socket) return;

    const payload = JSON.stringify({
      deviceId: this.deviceId,
      deviceName: config.deviceName,
      tcpPort: config.tcpPort,
      os: config.osType
    });

    const message = Buffer.from(payload);
    
    // Broadcast to local subnet
    this.socket.send(message, 0, message.length, config.udpPort, '255.255.255.255', (err) => {
      if (err) {
        // Ignore network unreachable errors (e.g. if Wi-Fi disconnected temporarily)
      }
    });
  }

  cleanupStalePeers() {
    const now = Date.now();
    let changed = false;

    for (const [id, peer] of this.peers.entries()) {
      if (now - peer.lastSeen > 15000) { // 15 seconds offline timeout
        console.log(`[Discovery] Peer went offline: ${peer.name} (${peer.ip})`);
        this.peers.delete(id);
        changed = true;
      }
    }

    if (changed) {
      this.notifyPeersChanged();
    }
  }

  notifyPeersChanged() {
    websocketService.broadcast('PEERS_UPDATED', this.getActivePeers());
  }

  getActivePeers() {
    return Array.from(this.peers.values()).map(p => ({
      id: p.id,
      name: p.name,
      ip: p.ip,
      port: p.port,
      os: p.os
    }));
  }

  stop() {
    if (this.broadcastInterval) clearInterval(this.broadcastInterval);
    if (this.cleanupInterval) clearInterval(this.cleanupInterval);
    if (this.socket) {
      try {
        this.socket.close();
      } catch (err) {}
      this.socket = null;
    }
  }
}

const discoveryService = new DiscoveryService();
export default discoveryService;
