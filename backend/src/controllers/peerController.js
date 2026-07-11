import path from 'path';
import fs from 'fs';
import discoveryService from '../services/discoveryService.js';
import tcpTransferService from '../services/tcpTransferService.js';
import * as storageService from '../services/storageService.js';

// Get list of discovered peers on the LAN
export const getPeers = (req, res) => {
  try {
    const peers = discoveryService.getActivePeers();
    res.json({ success: true, peers });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
};

// Initiate sending a file/folder to another peer
export const sendToPeer = async (req, res) => {
  const { peerIp, peerPort, fileName, filePath } = req.body;

  if (!peerIp || !peerPort) {
    return res.status(400).json({ success: false, error: 'Peer IP and Port are required' });
  }

  if (!fileName && !filePath) {
    return res.status(400).json({ success: false, error: 'Either fileName or absolute filePath is required' });
  }

  try {
    // If a filename is provided, look up in the local storage directory. Otherwise use absolute path.
    const targetPath = filePath ? path.resolve(filePath) : storageService.getSafePath(fileName);
    
    if (!fs.existsSync(targetPath)) {
      return res.status(404).json({ success: false, error: `File not found at: ${targetPath}` });
    }

    // Run async transfer. TCP client handles zipping on-the-fly if directory
    tcpTransferService.sendFile(peerIp, parseInt(peerPort, 10), targetPath)
      .then(() => {
        // Success logged internally
      })
      .catch((err) => {
        console.error(`P2P Send failed:`, err.message);
      });

    res.json({ success: true, message: 'Transfer initiated' });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
};

// Accept an incoming file transfer
export const acceptTransfer = async (req, res) => {
  const { transferId } = req.params;
  try {
    await tcpTransferService.acceptTransfer(transferId);
    res.json({ success: true, message: 'Transfer accepted' });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
};

// Reject an incoming file transfer
export const rejectTransfer = (req, res) => {
  const { transferId } = req.params;
  try {
    tcpTransferService.rejectTransfer(transferId);
    res.json({ success: true, message: 'Transfer rejected' });
  } catch (err) {
    res.status(400).json({ success: false, error: err.message });
  }
};

// List files in the local storage directory
export const getLocalFiles = async (req, res) => {
  try {
    const files = await storageService.listFiles();
    res.json({ success: true, files });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
};

// Delete a file/folder in the local storage directory
export const deleteLocalFile = async (req, res) => {
  const { fileName } = req.params;
  try {
    await storageService.deleteFile(fileName);
    res.json({ success: true, message: `Deleted ${fileName} successfully` });
  } catch (err) {
    res.status(404).json({ success: false, error: err.message });
  }
};

// Download a file directly from the local storage directory (e.g. into the browser)
export const downloadLocalFile = (req, res) => {
  const { fileName } = req.params;
  try {
    const filePath = storageService.getSafePath(fileName);
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ success: false, error: 'File not found' });
    }
    res.download(filePath, fileName, (err) => {
      if (err && !res.headersSent) {
        res.status(500).json({ success: false, error: 'Failed to download file' });
      }
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
};

// Handle file uploaded from the local client browser
export const uploadLocalFile = (req, res) => {
  try {
    if (!req.files || req.files.length === 0) {
      return res.status(400).json({ success: false, error: 'No files were uploaded' });
    }

    const uploadedFiles = req.files.map(f => ({
      name: f.originalname,
      size: f.size,
      path: f.path
    }));

    res.status(201).json({
      success: true,
      message: 'Files uploaded locally successfully',
      files: uploadedFiles
    });
  } catch (err) {
    res.status(500).json({ success: false, error: err.message });
  }
};
