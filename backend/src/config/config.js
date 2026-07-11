import dotenv from 'dotenv';
import path from 'path';
import os from 'os';
import fs from 'fs';

dotenv.config();

// Helper to expand '~' to user's home directory
const expandHomeDir = (filepath) => {
  if (!filepath) return '';
  if (filepath.startsWith('~')) {
    return path.join(os.homedir(), filepath.slice(1));
  }
  return path.resolve(filepath);
};

// Detect local network IP address
const getLocalIP = () => {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const net of interfaces[name]) {
      // Skip internal (loopback) and non-IPv4 addresses
      if (net.family === 'IPv4' && !net.internal) {
        return net.address;
      }
    }
  }
  return '127.0.0.1';
};

class Config {
  constructor() {
    this.port = parseInt(process.env.PORT, 10) || 5050;
    this.tcpPort = parseInt(process.env.TCP_PORT, 10) || 5051;
    this.udpPort = parseInt(process.env.UDP_PORT, 10) || 8585;
    
    // Resolve base storage path
    const envStoragePath = process.env.STORAGE_PATH || '~/Downloads/LocalShare';
    this.storagePath = expandHomeDir(envStoragePath);
    
    // Resolve device name
    this.deviceName = process.env.DEVICE_NAME || os.hostname() || 'Unknown Device';
    this.localIp = getLocalIP();
    this.osType = os.platform(); // 'darwin' (macOS), 'win32' (Windows), 'linux', etc.
  }

  // Dynamically update the storage path at runtime
  setStoragePath(newPath) {
    if (!newPath) throw new Error('Storage path cannot be empty');
    const resolved = expandHomeDir(newPath);
    // Try to create the directory structure recursively to ensure it is writeable
    if (!fs.existsSync(resolved)) {
      fs.mkdirSync(resolved, { recursive: true });
    } else {
      // Validate write access by creating a temporary file
      const tempFile = path.join(resolved, `.write_test_${Date.now()}`);
      fs.writeFileSync(tempFile, 'test');
      fs.unlinkSync(tempFile);
    }
    this.storagePath = resolved;
    return resolved;
  }

  // Dynamically update the device name
  setDeviceName(newName) {
    if (newName && newName.trim()) {
      this.deviceName = newName.trim();
    }
  }

  // Get current config payload
  get() {
    return {
      port: this.port,
      tcpPort: this.tcpPort,
      udpPort: this.udpPort,
      storagePath: this.storagePath,
      deviceName: this.deviceName,
      localIp: this.localIp,
      osType: this.osType,
    };
  }
}

const configInstance = new Config();
export default configInstance;
