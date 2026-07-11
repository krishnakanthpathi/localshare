import { WebSocketServer } from 'ws';

class WebSocketService {
  constructor() {
    this.wss = null;
    this.clients = new Set();
    this.messageHandlers = new Map();
  }

  // Initialize WS server attached to the HTTP server
  initialize(server) {
    this.wss = new WebSocketServer({ server });

    this.wss.on('connection', (ws) => {
      this.clients.add(ws);
      console.log('Local frontend client connected to WebSockets.');

      ws.on('message', (message) => {
        try {
          const payload = JSON.parse(message);
          this.handleMessage(ws, payload);
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      });

      ws.on('close', () => {
        this.clients.delete(ws);
        console.log('Local frontend client disconnected from WebSockets.');
      });

      ws.on('error', (err) => {
        console.error('WebSocket client socket error:', err);
        this.clients.delete(ws);
      });
    });
  }

  // Register handlers for messages sent from the frontend to the backend via WS
  registerHandler(type, handler) {
    this.messageHandlers.set(type, handler);
  }

  handleMessage(ws, payload) {
    const { type, data } = payload;
    const handler = this.messageHandlers.get(type);
    if (handler) {
      handler(ws, data);
    } else {
      console.warn(`No handler registered for WebSocket message type: ${type}`);
    }
  }

  // Broadcast events to all open frontend sessions
  broadcast(type, data) {
    if (!this.wss) return;
    const payload = JSON.stringify({ type, data });
    for (const client of this.clients) {
      if (client.readyState === 1) { // Check if OPEN (1)
        client.send(payload);
      }
    }
  }

  // Forcefully terminate all active WebSocket clients and close server
  stop() {
    if (this.wss) {
      console.log('[WS] Terminating all active client connections...');
      for (const client of this.clients) {
        try {
          client.terminate();
        } catch (err) {}
      }
      this.clients.clear();
      try {
        this.wss.close();
      } catch (err) {}
      this.wss = null;
    }
  }
}

const websocketService = new WebSocketService();
export default websocketService;
