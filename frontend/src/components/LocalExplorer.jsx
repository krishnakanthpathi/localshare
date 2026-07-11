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
  const [selectedFile, setSelectedFile] = useState(null);
  const [showShareMenu, setShowShareMenu] = useState(null); // fileName
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

  const triggerQuickShare = async (peer, fileName) => {
    setShowShareMenu(null);
    await onSendFile(peer, fileName);
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
                      <div className="relative">
                        <button
                          onClick={() => setShowShareMenu(showShareMenu === file.name ? null : file.name)}
                          className="p-2 text-gray-400 hover:text-primary-neon rounded-lg hover:bg-white/5 transition-all cursor-pointer"
                          title="Share with network peer"
                        >
                          <Send className="w-4 h-4" />
                        </button>

                        {/* Inline Share Peer Dropdown */}
                        {showShareMenu === file.name && (
                          <div className="absolute right-0 bottom-10 z-30 w-48 py-1 rounded-xl glass border border-white/10 shadow-2xl animate-fade-in text-left">
                            <div className="px-3 py-1.5 text-xs font-semibold text-gray-400 border-b border-white/5">
                              Send to peer:
                            </div>
                            {peers.map((peer) => (
                              <button
                                key={peer.id}
                                onClick={() => triggerQuickShare(peer, file.name)}
                                className="w-full px-3 py-2 text-xs text-white hover:bg-primary-neon/20 hover:text-white transition-all text-left flex items-center gap-2 cursor-pointer"
                              >
                                <div className="w-1.5 h-1.5 rounded-full bg-primary-neon"></div>
                                <span className="truncate flex-1">{peer.name}</span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
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
    </div>
  );
}
