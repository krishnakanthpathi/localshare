import React from 'react';
import { ArrowDownCircle, ArrowUpCircle, CheckCircle, AlertCircle, Loader, X, XCircle } from 'lucide-react';

const formatBytes = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export default function TransferTracker({ transfers, onCancel }) {
  const activeList = Object.values(transfers);
  if (activeList.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-40 w-full max-w-sm flex flex-col gap-3 p-4 glass rounded-2xl border-white/10 shadow-2xl animate-slide-up">
      <div className="flex items-center justify-between border-b border-white/5 pb-2">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Loader className="w-4 h-4 text-primary-neon animate-spin" />
          Active Transfers ({activeList.length})
        </h3>
      </div>

      <div className="flex flex-col gap-3 max-h-[300px] overflow-y-auto pr-1">
        {activeList.map((transfer) => {
          const { transferId, fileName, bytesReceived, fileSize, status, direction, error } = transfer;
          
          // Calculate percentage safely
          const percent = fileSize > 0 ? Math.round((bytesReceived / fileSize) * 100) : 0;
          
          const isInbound = direction === 'INBOUND';
          const isCompleted = status === 'COMPLETED';
          const isCancelled = status === 'CANCELLED';
          const isFailed = status === 'FAILED' || status === 'REJECTED';

          return (
            <div key={transferId} className="p-3 rounded-xl bg-white/5 border border-white/5 flex flex-col gap-2 relative group">
              {/* Cancel Button */}
              {!isCompleted && !isFailed && !isCancelled && (
                <button
                  onClick={() => onCancel(transferId)}
                  className="absolute top-2 right-2 p-1 text-gray-500 hover:text-red-400 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
                  title="Cancel Transfer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}

              <div className="flex items-center gap-3">
                {/* Direction Icons */}
                <div className="flex-shrink-0">
                  {isCompleted ? (
                    <CheckCircle className="w-5 h-5 text-success-neon animate-scale-up" />
                  ) : isCancelled ? (
                    <XCircle className="w-5 h-5 text-gray-500 animate-scale-up" />
                  ) : isFailed ? (
                    <AlertCircle className="w-5 h-5 text-red-400" />
                  ) : isInbound ? (
                    <ArrowDownCircle className="w-5 h-5 text-secondary-neon animate-pulse" />
                  ) : (
                    <ArrowUpCircle className="w-5 h-5 text-primary-neon animate-pulse" />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <h4 className="text-xs font-semibold text-white truncate pr-4" title={fileName}>
                    {fileName}
                  </h4>
                  <div className="flex items-center justify-between text-[10px] text-gray-400 mt-0.5">
                    <span>
                      {isCompleted 
                        ? 'Finished' 
                        : isCancelled
                          ? 'Cancelled'
                          : isFailed 
                            ? status === 'REJECTED' ? 'Rejected by peer' : 'Error occurred'
                            : `${formatBytes(bytesReceived)} / ${formatBytes(fileSize)}`
                      }
                    </span>
                    <span className="font-bold text-white">
                      {isCompleted ? '100%' : isCancelled ? '0%' : `${percent}%`}
                    </span>
                  </div>
                </div>
              </div>

              {/* Progress Bar */}
              {!isCompleted && !isFailed && !isCancelled && (
                <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-300 rounded-full ${
                      isInbound 
                        ? 'bg-gradient-to-r from-secondary-neon to-cyan-400' 
                        : 'bg-gradient-to-r from-primary-neon to-purple-400'
                    }`}
                    style={{ width: `${percent}%` }}
                  ></div>
                </div>
              )}

              {/* Error messages */}
              {isFailed && error && (
                <p className="text-[10px] text-red-400 truncate max-w-full" title={error}>
                  {error}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
