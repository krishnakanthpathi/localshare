import { Router } from 'express';
import * as peerController from '../controllers/peerController.js';
import upload from '../middleware/upload.js';

const router = Router();

// Retrieve discovered peers on the LAN
router.get('/', peerController.getPeers);

// Trigger sending a file/folder from local machine to a peer
router.post('/send', peerController.sendToPeer);

// Handshake accept/reject for incoming raw TCP file transfers
router.post('/transfers/:transferId/accept', peerController.acceptTransfer);
router.post('/transfers/:transferId/reject', peerController.rejectTransfer);

// Local file repository endpoints
router.get('/files', peerController.getLocalFiles);
router.delete('/files/:fileName', peerController.deleteLocalFile);
router.get('/files/download/:fileName', peerController.downloadLocalFile);

// Endpoint for browser to upload files locally
router.post('/files/upload', upload.array('files'), peerController.uploadLocalFile);

export default router;
