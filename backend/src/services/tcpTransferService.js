import net from 'net';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { Transform, PassThrough } from 'stream';
import config from '../config/config.js';
import websocketService from './websocketService.js';
import { getStoragePath, ensureDirExists, extractZipStream, createZipStream } from './storageService.js';

class ProgressStream extends Transform {
  constructor(onProgress) {
    super();
    this.onProgress = onProgress;
  }
  _transform(chunk, encoding, callback) {
    this.onProgress(chunk.length);
    callback(null, chunk);
  }
}

// Helper to resolve unique file path if it already exists
const getUniqueFilePath = (dir, filename) => {
  const ext = path.extname(filename);
  const name = path.basename(filename, ext);
  let filePath = path.join(dir, filename);
  let counter = 1;
  while (fs.existsSync(filePath)) {
    filePath = path.join(dir, `${name} (${counter})${ext}`);
    counter++;
  }
  return filePath;
};

class TcpTransferService {
  constructor() {
    this.server = null;
    this.pendingTransfers = new Map(); // transferId -> { socket, metadata, remaining }
    this.activeTransfers = new Map();  // transferId -> { bytesReceived, fileSize, status, fileName }
  }

  start() {
    const port = config.tcpPort;
    this.server = net.createServer((socket) => {
      console.log(`[TCP Server] Connection received from ${socket.remoteAddress}`);
      
      let buffer = Buffer.alloc(0);
      let headerLength = null;
      let handshaked = false;

      const handleData = (chunk) => {
        if (handshaked) return;

        buffer = Buffer.concat([buffer, chunk]);

        if (headerLength === null) {
          if (buffer.length >= 4) {
            headerLength = buffer.readUInt32BE(0);
            buffer = buffer.slice(4);
          } else {
            return; // Wait for header length
          }
        }

        if (headerLength !== null && buffer.length >= headerLength) {
          handshaked = true;
          socket.removeListener('data', handleData);

          try {
            const jsonStr = buffer.slice(0, headerLength).toString('utf8');
            const metadata = JSON.parse(jsonStr);
            const remaining = buffer.slice(headerLength);

            const transferId = `transfer_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
            
            // Store pending socket and data
            this.pendingTransfers.set(transferId, {
              socket,
              metadata,
              remaining
            });

            console.log(`[TCP Server] Received transfer proposal for: "${metadata.fileName}" (${metadata.fileSize} bytes) from "${metadata.senderName}"`);

            // Pause reading socket buffer until approved
            socket.pause();

            // Notify local frontend of incoming file prompt
            websocketService.broadcast('INCOMING_TRANSFER_PROMPT', {
              transferId,
              fileName: metadata.fileName,
              fileSize: metadata.fileSize,
              isFolder: metadata.isFolder,
              senderName: metadata.senderName
            });

            // Handle client disconnecting while prompt is open
            socket.once('close', () => {
              if (this.pendingTransfers.has(transferId)) {
                this.pendingTransfers.delete(transferId);
                console.log(`[TCP Server] Pending transfer "${metadata.fileName}" connection closed by sender.`);
                websocketService.broadcast('TRANSFER_CANCELLED', { transferId });
              }
            });

            socket.once('error', (err) => {
              console.error(`[TCP Server] Socket error for pending transfer:`, err.message);
              this.pendingTransfers.delete(transferId);
              websocketService.broadcast('TRANSFER_ERROR', { transferId, error: err.message });
            });

          } catch (err) {
            console.error('[TCP Server] Failed to parse metadata header:', err);
            socket.write('ERROR\n');
            socket.destroy();
          }
        }
      };

      socket.on('data', handleData);
    });

    this.server.listen(port, '0.0.0.0', () => {
      console.log(`[TCP Server] Listening for incoming files on port ${port}`);
    });
  }

  async acceptTransfer(transferId) {
    const transfer = this.pendingTransfers.get(transferId);
    if (!transfer) {
      throw new Error('Transfer request not found or expired');
    }

    const { socket, metadata, remaining } = transfer;
    this.pendingTransfers.delete(transferId); // Move to active

    // Clean up temporary pending-state event listeners
    socket.removeAllListeners('close');
    socket.removeAllListeners('error');
    socket.removeAllListeners('end');

    const baseDir = getStoragePath();
    let filePath = '';
    let writeStream = null;

    console.log(`[TCP Server] Accepted file transfer for: ${metadata.fileName}`);

    // Track active receive progress
    const activeInfo = {
      bytesReceived: 0,
      fileSize: metadata.fileSize,
      status: 'RECEIVING',
      fileName: metadata.fileName,
      isFolder: metadata.isFolder
    };
    this.activeTransfers.set(transferId, activeInfo);

    // Notify sender we are ready to stream
    socket.write('ACCEPT\n');

    let extractionPromise = null;

    if (metadata.isFolder) {
      const folderName = metadata.fileName.endsWith('.zip') 
        ? metadata.fileName.substring(0, metadata.fileName.length - 4) 
        : metadata.fileName;
      
      const targetFolder = getUniqueFilePath(baseDir, folderName);
      ensureDirExists(targetFolder);

      let lastProgressUpdate = 0;
      const progress = new ProgressStream((bytes) => {
        activeInfo.bytesReceived += bytes;
        const now = Date.now();
        if (now - lastProgressUpdate > 500) {
          lastProgressUpdate = now;
          websocketService.broadcast('TRANSFER_PROGRESS', {
            transferId,
            bytesReceived: activeInfo.bytesReceived,
            fileSize: metadata.fileSize
          });
        }
      });

      const unifiedStream = new PassThrough();
      extractionPromise = extractZipStream(unifiedStream.pipe(progress), targetFolder);

      if (remaining.length > 0) {
        unifiedStream.write(remaining);
      }
      socket.pipe(unifiedStream);

    } else {
      filePath = getUniqueFilePath(baseDir, metadata.fileName);
      writeStream = fs.createWriteStream(filePath);

      let lastProgressUpdate = 0;
      const progress = new ProgressStream((bytes) => {
        activeInfo.bytesReceived += bytes;
        const now = Date.now();
        if (now - lastProgressUpdate > 500) {
          lastProgressUpdate = now;
          websocketService.broadcast('TRANSFER_PROGRESS', {
            transferId,
            bytesReceived: activeInfo.bytesReceived,
            fileSize: metadata.fileSize
          });
        }
      });

      if (remaining.length > 0) {
        writeStream.write(remaining);
        activeInfo.bytesReceived += remaining.length;
      }

      socket.pipe(progress).pipe(writeStream);
    }

    // Resume reading TCP socket data
    socket.resume();

    const completeTransfer = () => {
      activeInfo.status = 'COMPLETED';
      activeInfo.bytesReceived = metadata.fileSize;
      console.log(`[TCP Server] Completed file transfer: ${metadata.fileName}`);
      
      websocketService.broadcast('TRANSFER_COMPLETE', {
        transferId,
        fileName: metadata.fileName,
        isFolder: metadata.isFolder,
        filePath: filePath || 'Folder structure extracted'
      });
      
      // Update file list on frontend
      websocketService.broadcast('FILES_CHANGED', {});
      
      socket.destroy();
      this.activeTransfers.delete(transferId);
    };

    const handleTransferError = (err) => {
      console.error(`[TCP Server] Transfer error for ${metadata.fileName}:`, err.message);
      activeInfo.status = 'FAILED';
      websocketService.broadcast('TRANSFER_ERROR', { transferId, error: err.message });
      socket.destroy();
      this.activeTransfers.delete(transferId);
      
      // Clean up corrupt/partial files
      if (filePath && fs.existsSync(filePath)) {
        fs.unlink(filePath, () => {});
      }
    };

    socket.on('error', handleTransferError);
    socket.on('close', () => {
      if (activeInfo.status === 'RECEIVING' && activeInfo.bytesReceived < metadata.fileSize) {
        // If closed prematurely
        handleTransferError(new Error('Connection closed by peer before completion'));
      }
    });

    if (metadata.isFolder && extractionPromise) {
      extractionPromise
        .then(completeTransfer)
        .catch(handleTransferError);
    } else if (writeStream) {
      writeStream.on('finish', completeTransfer);
      writeStream.on('error', handleTransferError);
    }
  }

  rejectTransfer(transferId) {
    const transfer = this.pendingTransfers.get(transferId);
    if (!transfer) {
      throw new Error('Transfer request not found or expired');
    }

    const { socket, metadata } = transfer;
    this.pendingTransfers.delete(transferId);

    console.log(`[TCP Server] Rejected file transfer: ${metadata.fileName}`);
    try {
      socket.write('REJECT\n');
      socket.destroy();
    } catch (err) {}

    websocketService.broadcast('TRANSFER_REJECTED', { transferId });
  }

  // Client (Sender) Side: Sends a file or folder to a peer
  sendFile(peerIp, peerPort, localPath) {
    return new Promise((resolve, reject) => {
      if (!fs.existsSync(localPath)) {
        return reject(new Error(`File or directory does not exist: ${localPath}`));
      }

      const stats = fs.statSync(localPath);
      const isFolder = stats.isDirectory();
      const baseName = path.basename(localPath);
      const transferId = `send_${Date.now()}`;
      
      let tempZipPath = null;
      let fileSize = stats.size;
      let fileName = baseName;

      const proceedWithTransfer = (actualPath, finalSize, finalName) => {
        console.log(`[TCP Client] Connecting to peer at ${peerIp}:${peerPort} for sending: ${finalName}`);
        
        const client = net.createConnection({ host: peerIp, port: peerPort }, () => {
          console.log(`[TCP Client] Connected. Transmitting metadata header...`);
          
          // Construct protocol header
          const metadata = JSON.stringify({
            fileName: finalName,
            fileSize: finalSize,
            isFolder: isFolder,
            senderName: config.deviceName
          });
          
          const metadataBuf = Buffer.from(metadata, 'utf8');
          const lengthBuf = Buffer.alloc(4);
          lengthBuf.writeUInt32BE(metadataBuf.length, 0);

          client.write(lengthBuf);
          client.write(metadataBuf);
        });

        let responseBuffer = '';
        const handleResponse = (data) => {
          responseBuffer += data.toString();
          if (responseBuffer.includes('\n')) {
            client.removeListener('data', handleResponse);
            
            const response = responseBuffer.trim();
            if (response === 'ACCEPT') {
              console.log(`[TCP Client] Peer accepted file. Streaming data...`);
              websocketService.broadcast('SEND_STARTED', { transferId, fileName: finalName });

              const fileStream = fs.createReadStream(actualPath);
              let lastProgressUpdate = 0;
              let sentBytes = 0;

              const progress = new ProgressStream((bytes) => {
                sentBytes += bytes;
                const now = Date.now();
                if (now - lastProgressUpdate > 500) {
                  lastProgressUpdate = now;
                  websocketService.broadcast('SEND_PROGRESS', {
                    transferId,
                    bytesSent: sentBytes,
                    fileSize: finalSize
                  });
                }
              });

              fileStream.pipe(progress).pipe(client);

              fileStream.on('error', (err) => {
                console.error(`[TCP Client] Error reading file stream:`, err);
                client.destroy();
                cleanupTempZip();
                reject(err);
              });

              client.on('close', () => {
                console.log(`[TCP Client] Stream sent successfully.`);
                websocketService.broadcast('SEND_COMPLETE', { transferId });
                cleanupTempZip();
                resolve();
              });

            } else if (response === 'REJECT') {
              console.log(`[TCP Client] Peer rejected the transfer.`);
              websocketService.broadcast('SEND_REJECTED', { transferId });
              client.destroy();
              cleanupTempZip();
              reject(new Error('Transfer rejected by receiving peer'));
            } else {
              console.error(`[TCP Client] Unknown handshake response: ${response}`);
              client.destroy();
              cleanupTempZip();
              reject(new Error(`Handshake protocol error: ${response}`));
            }
          }
        };

        client.on('data', handleResponse);

        client.on('error', (err) => {
          console.error(`[TCP Client] Socket error:`, err.message);
          cleanupTempZip();
          reject(err);
        });
      };

      const cleanupTempZip = () => {
        if (tempZipPath && fs.existsSync(tempZipPath)) {
          try {
            fs.unlinkSync(tempZipPath);
          } catch (err) {}
        }
      };

      if (isFolder) {
        fileName = `${baseName}.zip`;
        tempZipPath = path.join(os.tmpdir(), `localshare_${Date.now()}_${Math.random().toString(36).substring(2, 6)}.zip`);
        
        console.log(`[TCP Client] Zipping folder structure: "${localPath}" -> "${tempZipPath}"`);
        
        const output = fs.createWriteStream(tempZipPath);
        const zipStream = createZipStream(localPath);
        
        zipStream.pipe(output);
        output.on('close', () => {
          const zipStats = fs.statSync(tempZipPath);
          proceedWithTransfer(tempZipPath, zipStats.size, fileName);
        });
        
        zipStream.on('error', (err) => {
          console.error('[TCP Client] Folder archiving failed:', err);
          cleanupTempZip();
          reject(err);
        });
      } else {
        proceedWithTransfer(localPath, fileSize, fileName);
      }
    });
  }

  stop() {
    if (this.server) {
      try {
        this.server.close();
      } catch (err) {}
      this.server = null;
    }
    for (const transfer of this.pendingTransfers.values()) {
      try {
        transfer.socket.destroy();
      } catch (err) {}
    }
    this.pendingTransfers.clear();
    this.activeTransfers.clear();
  }
}

const tcpTransferService = new TcpTransferService();
export default tcpTransferService;
