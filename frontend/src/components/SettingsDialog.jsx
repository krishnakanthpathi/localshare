import React, { useState, useEffect } from 'react';
import { Settings, Folder, User, X, Check } from 'lucide-react';

export default function SettingsDialog({ currentConfig, onSave, onClose }) {
  const [deviceName, setDeviceName] = useState('');
  const [storagePath, setStoragePath] = useState('');
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (currentConfig) {
      setDeviceName(currentConfig.deviceName || '');
      setStoragePath(currentConfig.storagePath || '');
    }
  }, [currentConfig]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    setSaving(true);

    try {
      const result = await onSave({ deviceName, storagePath });
      if (result.success) {
        setSuccess(true);
        setTimeout(() => {
          setSuccess(false);
          onClose();
        }, 1200);
      } else {
        setError(result.error || 'Failed to save configuration');
      }
    } catch (err) {
      setError(err.message || 'An unexpected error occurred');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-md overflow-hidden rounded-2xl glass shadow-2xl border-white/10 animate-scale-up">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-white/5">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-primary-neon" />
            <h3 className="font-semibold text-lg text-white">LocalShare Settings</h3>
          </div>
          <button 
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-white/5 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-5">
          {/* Device Name Input */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold text-gray-400 flex items-center gap-1.5 uppercase tracking-wider">
              <User className="w-3.5 h-3.5 text-primary-neon" />
              Device Name
            </label>
            <input
              type="text"
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              placeholder="e.g. Krishnakanth's MacBook"
              required
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-primary-neon focus:ring-1 focus:ring-primary-neon/30 transition-all"
            />
          </div>

          {/* Storage Directory Input */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold text-gray-400 flex items-center gap-1.5 uppercase tracking-wider">
              <Folder className="w-3.5 h-3.5 text-secondary-neon" />
              macOS Storage Directory
            </label>
            <input
              type="text"
              value={storagePath}
              onChange={(e) => setStoragePath(e.target.value)}
              placeholder="e.g. ~/Downloads/LocalShare"
              required
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-secondary-neon focus:ring-1 focus:ring-secondary-neon/30 transition-all"
            />
            <p className="text-[10px] text-gray-500 leading-normal mt-0.5">
              Supports absolute system directories. If the path does not exist, it will be automatically created recursively on the host operating system.
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3.5 rounded-xl border border-red-500/20 bg-red-500/10 text-xs text-red-400 leading-relaxed">
              <strong>Configuration Error:</strong> {error}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex gap-4 mt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="flex-1 px-4 py-3 rounded-xl border border-white/10 hover:bg-white/5 text-gray-300 font-medium transition-all cursor-pointer text-sm disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className={`flex-grow-[1.5] px-4 py-3 rounded-xl text-white font-bold transition-all cursor-pointer text-sm flex items-center justify-center gap-2 ${
                success 
                  ? 'bg-success-neon shadow-lg shadow-success-neon/20' 
                  : 'bg-gradient-to-r from-primary-neon to-secondary-neon hover:opacity-95 shadow-lg shadow-primary-neon/25'
              }`}
            >
              {saving ? (
                'Saving Settings...'
              ) : success ? (
                <>
                  <Check className="w-4 h-4" />
                  Saved!
                </>
              ) : (
                'Save Changes'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
