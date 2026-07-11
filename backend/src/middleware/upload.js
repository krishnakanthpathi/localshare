import multer from 'multer';
import { getStoragePath, ensureDirExists } from '../services/storageService.js';

// Configure multer storage engine to dynamically reference the active config storage path
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    try {
      const uploadPath = getStoragePath();
      ensureDirExists(uploadPath);
      cb(null, uploadPath);
    } catch (err) {
      cb(err);
    }
  },
  filename: (req, file, cb) => {
    // Keep original file name when uploaded locally
    cb(null, file.originalname);
  }
});

const upload = multer({ storage });
export default upload;
