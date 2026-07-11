import express from 'express';
import cors from 'cors';
import peerRoutes from './routes/peerRoutes.js';
import systemRoutes from './routes/systemRoutes.js';

const app = express();

// Enable Cross-Origin Resource Sharing for all origins (useful in local P2P networks)
app.use(cors({
  origin: '*',
  methods: ['GET', 'POST', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// Body parsers
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Dynamic routes mount
app.use('/api/peers', peerRoutes);
app.use('/api/system', systemRoutes);

// Base sanity check
app.get('/health', (req, res) => {
  res.json({ status: 'OK', timestamp: new Date().toISOString() });
});

// Fallback 404 handler
app.use((req, res, next) => {
  res.status(404).json({ success: false, error: `Route ${req.method} ${req.url} not found` });
});

// Centralized error handling middleware
app.use((err, req, res, next) => {
  console.error('[Express Error]', err);
  res.status(err.status || 500).json({
    success: false,
    error: err.message || 'Internal Server Error'
  });
});

export default app;
