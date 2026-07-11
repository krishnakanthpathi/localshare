import { Router } from 'express';
import * as systemController from '../controllers/systemController.js';

const router = Router();

// Retrieve active configurations (local IP, storage folder path, device name)
router.get('/config', systemController.getConfig);

// Modify active configurations at runtime (updates local name or file storage directory)
router.post('/config', systemController.updateConfig);

export default router;
