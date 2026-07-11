import fs from 'fs';
import path from 'path';
import { ZipArchive } from 'archiver';
import unzipper from 'unzipper';
import config from '../config/config.js';

export const ensureDirExists = (dirPath) => {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
};

export const getStoragePath = () => {
  const p = config.storagePath;
  ensureDirExists(p);
  return p;
};

// Safe path resolver to prevent directory traversal attacks
export const getSafePath = (fileName) => {
  const base = getStoragePath();
  const safeName = path.normalize(fileName).replace(/^(\.\.(\/|\\|$))+/, '');
  return path.join(base, safeName);
};

// List files in the storage path
export const listFiles = async () => {
  const base = getStoragePath();
  try {
    const files = await fs.promises.readdir(base, { withFileTypes: true });
    const list = [];
    for (const file of files) {
      if (file.name.startsWith('.')) continue; // ignore hidden files
      const fullPath = path.join(base, file.name);
      try {
        const stats = await fs.promises.stat(fullPath);
        list.push({
          name: file.name,
          size: stats.size,
          modified: stats.mtime,
          isFolder: file.isDirectory(),
        });
      } catch (err) {
        console.error(`Error statting file ${file.name}:`, err);
      }
    }
    // Return files ordered by modification date (newest first)
    return list.sort((a, b) => b.modified - a.modified);
  } catch (err) {
    console.error('Error reading storage directory:', err);
    return [];
  }
};

// Delete a file or directory
export const deleteFile = async (fileName) => {
  const fullPath = getSafePath(fileName);
  if (!fs.existsSync(fullPath)) {
    throw new Error('File not found');
  }
  const stats = await fs.promises.stat(fullPath);
  if (stats.isDirectory()) {
    await fs.promises.rm(fullPath, { recursive: true, force: true });
  } else {
    await fs.promises.unlink(fullPath);
  }
};

// Create a ZIP stream from a local folder or file path
export const createZipStream = (sourcePath) => {
  const archive = new ZipArchive({
    zlib: { level: 9 }, // standard compression
  });

  const stats = fs.statSync(sourcePath);
  if (stats.isDirectory()) {
    archive.directory(sourcePath, false);
  } else {
    archive.file(sourcePath, { name: path.basename(sourcePath) });
  }

  // We finalize immediately so the zip starts writing to its piped output stream
  archive.finalize();
  return archive;
};

// Pipe a readable stream of a zip archive directly through unzipper to a target directory
export const extractZipStream = (inputStream, destDir) => {
  ensureDirExists(destDir);
  return new Promise((resolve, reject) => {
    inputStream
      .pipe(unzipper.Extract({ path: destDir }))
      .on('close', () => resolve())
      .on('entry', (entry) => {
        // Log entries for monitoring extraction
        console.log(`Extracting: ${entry.path}`);
      })
      .on('error', (err) => reject(err));
  });
};
