import http from 'http';
import app from './src/app.js';
import config from './src/config/config.js';
import websocketService from './src/services/websocketService.js';
import discoveryService from './src/services/discoveryService.js';
import tcpTransferService from './src/services/tcpTransferService.js';
import { ensureDirExists } from './src/services/storageService.js';

const server = http.createServer(app);

// Initialize WebSocket notifications server
websocketService.initialize(server);

// Setup dynamic acceptor/rejector handlers for WebSocket events
websocketService.registerHandler('ACCEPT_TRANSFER', async (ws, data) => {
  try {
    const { transferId } = data;
    await tcpTransferService.acceptTransfer(transferId);
  } catch (err) {
    ws.send(JSON.stringify({ type: 'ERROR', data: { message: err.message } }));
  }
});

websocketService.registerHandler('REJECT_TRANSFER', (ws, data) => {
  try {
    const { transferId } = data;
    tcpTransferService.rejectTransfer(transferId);
  } catch (err) {
    ws.send(JSON.stringify({ type: 'ERROR', data: { message: err.message } }));
  }
});

// Setup fallback server port listener
const port = config.port;

const startServer = async () => {
  try {
    // 1. Ensure storage directory exists
    ensureDirExists(config.storagePath);
    console.log(`[Storage] Storage directory initialized at: ${config.storagePath}`);

    // 2. Start TCP transfer listener
    tcpTransferService.start();

    // 3. Start UDP Peer discovery broadcasts and scans
    discoveryService.start();

    // 4. Start HTTP & WebSocket server
    server.listen(port, '0.0.0.0', () => {
      console.log(`====================================================`);
      console.log(`LocalShare Server running on ${config.localIp}:${port}`);
      console.log(`Local WebSocket events endpoint ready.`);
      console.log(`Device Name: "${config.deviceName}"`);
      console.log(`Platform detected: ${config.osType}`);
      console.log(`====================================================`);
    });
  } catch (err) {
    console.error('Fatal server startup crash:', err);
    process.exit(1);
  }
};

// Graceful teardown on shutdown
const shutdown = () => {
  console.log('\nShutting down LocalShare server gracefully...');
  
  discoveryService.stop();
  tcpTransferService.stop();
  
  server.close(() => {
    console.log('HTTP & WebSocket servers closed.');
    process.exit(0);
  });
};

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

startServer();
