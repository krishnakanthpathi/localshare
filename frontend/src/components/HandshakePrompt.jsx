import React from 'react';
import { File, FolderArchive, Download, X } from 'lucide-react';

const formatBytes = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export default function HandshakePrompt({ prompt, onAccept, onReject }) {
  if (!prompt) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-md overflow-hidden rounded-2xl glass shadow-2xl border-white/10 animate-scale-up">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-white/5">
          <div className="flex items-center gap-2">
            <Download className="w-5 h-5 text-primary-neon animate-bounce" />
            <h3 className="font-semibold text-lg text-white">Incoming Transfer</h3>
          </div>
          <button 
            onClick={() => onReject(prompt.transferId)}
            className="p-1 text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-white/5"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 text-center">
          <div className="flex justify-center mb-4">
            <div className="p-4 rounded-full bg-primary-neon/15 border border-primary-neon/30 text-primary-neon">
              {prompt.isFolder ? (
                <FolderArchive className="w-10 h-10" />
              ) : (
                <File className="w-10 h-10" />
              )}
            </div>
          </div>

          <h4 className="text-xl font-bold text-white mb-1 truncate max-w-full px-2" title={prompt.fileName}>
            {prompt.fileName}
          </h4>
          <p className="text-gray-400 text-sm mb-4">
            Size: <span className="text-white font-medium">{formatBytes(prompt.fileSize)}</span>
          </p>

          <div className="p-4 rounded-xl bg-white/5 border border-white/5 text-sm text-left mb-6">
            <div className="flex justify-between items-center">
              <span className="text-gray-400">Sender:</span>
              <span className="text-white font-semibold">{prompt.senderName}</span>
            </div>
            <div className="flex justify-between items-center mt-2">
              <span className="text-gray-400">Format:</span>
              <span className="text-white font-medium">{prompt.isFolder ? 'Zipped Folder structure' : 'Single File'}</span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-4">
            <button
              onClick={() => onReject(prompt.transferId)}
              className="flex-1 px-4 py-3 rounded-xl border border-white/10 hover:border-red-500/30 hover:bg-red-500/10 text-white font-medium transition-all cursor-pointer text-sm"
            >
              Decline
            </button>
            <button
              onClick={() => onAccept(prompt.transferId)}
              className="flex-1 px-4 py-3 rounded-xl bg-gradient-to-r from-primary-neon to-secondary-neon hover:opacity-90 shadow-lg text-white font-bold transition-all cursor-pointer text-sm"
            >
              Accept File
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
