import React, { useState, useRef } from 'react';
import { 
  File, FolderArchive, FileText, FileImage, FileVideo, FileAudio, 
  Trash2, Download, UploadCloud, Send, ExternalLink 
} from 'lucide-react';

const formatBytes = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const getFileIcon = (fileName, isFolder) => {
  if (isFolder) return <FolderArchive className="w-5 h-5 text-yellow-500" />;
  
  const ext = fileName.split('.').pop().toLowerCase();
  if (['txt', 'md', 'pdf', 'doc', 'docx'].includes(ext)) {
    return <FileText className="w-5 h-5 text-blue-400" />;
  }
  if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'].includes(ext)) {
    return <FileImage className="w-5 h-5 text-green-400" />;
  }
  if (['mp4', 'mkv', 'avi', 'mov'].includes(ext)) {
    return <FileVideo className="w-5 h-5 text-red-400" />;
  }
  if (['mp3', 'wav', 'flac', 'ogg', 'm4a'].includes(ext)) {
    return <FileAudio className="w-5 h-5 text-emerald-400" />;
  }
  if (['zip', 'rar', 'tar', 'gz', '7z'].includes(ext)) {
    return <FolderArchive className="w-5 h-5 text-purple-400" />;
  }
  return <File className="w-5 h-5 text-gray-400" />;
};

export default function LocalExplorer({ files, peers, onUpload, onDelete, onSendFile }) {
  const [dragActive, setDragActive] = useState(false);
  const [shareFile, setShareFile] = useState(null); // file object for quick share modal
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await onUpload(e.dataTransfer.files);
    }
  };

  const handleFileInput = async (e) => {
    if (e.target.files && e.target.files.length > 0) {
      await onUpload(e.target.files);
      e.target.value = ''; // Reset input selection
    }
  };

  const triggerFileInput = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const downloadUrl = (fileName) => {
    return `http://${window.location.hostname}:5050/api/peers/files/download/${encodeURIComponent(fileName)}`;
  };

  return (
    <div className="w-full grid grid-cols-1 lg:grid-cols-3 gap-8">
      {/* File Repository Listing (2/3 width on wide screens) */}
      <div className="lg:col-span-2 flex flex-col h-full">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold text-white">Local Storage Directory</h2>
          <span className="text-sm text-gray-400">
            {files.length === 1 ? '1 item' : `${files.length} items`}
          </span>
        </div>

        <div className="glass rounded-2xl border-white/5 bg-white/5 overflow-hidden flex-1 flex flex-col max-h-[460px]">
          {files.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-gray-400">
              <File className="w-12 h-12 text-gray-500 mb-3" />
              <p className="text-sm">Storage directory is empty.</p>
              <p className="text-xs text-gray-500 mt-1">Upload files locally or accept incoming transfers to list files.</p>
            </div>
          ) : (
            <div className="overflow-y-auto divide-y divide-white/5">
              {files.map((file) => (
                <div key={file.name} className="flex items-center justify-between p-4 hover:bg-white/5 transition-all group">
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div className="p-2 rounded-lg bg-white/5 border border-white/5 text-gray-300">
                      {getFileIcon(file.name, file.isFolder)}
                    </div>
                    <div className="min-w-0">
                      <h4 className="text-sm font-semibold text-white truncate max-w-[200px] sm:max-w-xs md:max-w-md" title={file.name}>
                        {file.name}
                      </h4>
                      <p className="text-xs text-gray-400">
                        {formatBytes(file.size)} &bull; {new Date(file.modified).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 relative">
                    {/* Share Button (P2P Send) */}
                    {peers.length > 0 && (
                      <button
                        onClick={() => setShareFile(file)}
                        className="p-2 text-gray-400 hover:text-primary-neon rounded-lg hover:bg-white/5 transition-all cursor-pointer"
                        title="Share with network peer"
                      >
                        <Send className="w-4 h-4" />
                      </button>
                    )}

                    {/* Download to Browser */}
                    {!file.isFolder && (
                      <a
                        href={downloadUrl(file.name)}
                        download={file.name}
                        className="p-2 text-gray-400 hover:text-secondary-neon rounded-lg hover:bg-white/5 transition-all cursor-pointer"
                        title="Download to browser"
                      >
                        <Download className="w-4 h-4" />
                      </a>
                    )}

                    {/* Delete */}
                    <button
                      onClick={() => onDelete(file.name)}
                      className="p-2 text-gray-400 hover:text-red-400 rounded-lg hover:bg-white/5 transition-all cursor-pointer"
                      title="Delete file"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Drag & Drop Local Upload Box (1/3 width) */}
      <div className="lg:col-span-1 flex flex-col h-full">
        <h2 className="text-xl font-semibold text-white mb-4">Local Upload</h2>
        
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={triggerFileInput}
          className={`flex-1 min-h-[220px] flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-2xl glass transition-all cursor-pointer text-center select-none ${
            dragActive
              ? 'border-primary-neon bg-primary-neon/5 scale-[0.99]'
              : 'border-white/10 hover:border-white/20 hover:bg-white/5'
          }`}
        >
          <input
            type="file"
            multiple
            ref={fileInputRef}
            onChange={handleFileInput}
            className="hidden"
          />
          <UploadCloud className={`w-12 h-12 mb-3 transition-transform duration-300 ${dragActive ? 'scale-110 text-primary-neon' : 'text-gray-400 group-hover:scale-105'}`} />
          <h3 className="font-semibold text-white text-sm mb-1">Drag files here to add</h3>
          <p className="text-xs text-gray-400 max-w-[180px] mx-auto">
            or click to browse local files. Files are uploaded directly to your storage folder on the Mac.
          </p>
        </div>
      </div>

      {/* Quick Share Modal Overlay */}
      {shareFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl glass shadow-2xl border border-white/10 p-6 text-center animate-scale-up">
            <h3 className="font-bold text-lg text-white mb-2">Share File</h3>
            <p className="text-sm text-gray-400 mb-4">
              Select a peer to share <span className="text-white font-medium">"{shareFile.name}"</span>
            </p>
            <div className="flex flex-col gap-2 mb-6">
              {peers.map((peer) => (
                <button
                  key={peer.id}
                  onClick={() => {
                    onSendFile(peer, shareFile.name);
                    setShareFile(null);
                  }}
                  className="w-full flex items-center justify-between p-3.5 rounded-xl border border-white/10 hover:border-primary-neon hover:bg-primary-neon/10 transition-all text-white font-semibold cursor-pointer text-sm"
                >
                  <span>{peer.name}</span>
                  <span className="text-xs text-gray-400 font-mono">{peer.ip}</span>
                </button>
              ))}
            </div>
            <button
              onClick={() => setShareFile(null)}
              className="w-full py-2.5 rounded-xl border border-white/10 hover:bg-white/5 text-gray-300 font-medium transition-all cursor-pointer text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
