import React from 'react';
import { AuditLogItem } from '../../types/adminMenu';

interface AuditHistoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
  logs: AuditLogItem[];
  loading: boolean;
}

export const AuditHistoryPanel: React.FC<AuditHistoryPanelProps> = ({
  isOpen,
  onClose,
  logs,
  loading,
}) => {
  if (!isOpen) return null;

  const formatActionBadge = (action: string) => {
    switch (action) {
      case 'PRICE_CHANGE':
        return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      case 'AVAILABILITY_TOGGLE':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
      case 'ITEM_CREATE':
      case 'CATEGORY_CREATE':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'ITEM_UPDATE':
      case 'CATEGORY_UPDATE':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      default:
        return 'bg-slate-700/50 text-slate-300 border-slate-600';
    }
  };

  const renderMetadata = (meta: Record<string, any> | null) => {
    if (!meta) return null;
    return (
      <div className="mt-1 text-[11px] font-mono text-slate-400 space-y-0.5 bg-slate-950/60 p-2 rounded-lg border border-slate-800">
        {Object.entries(meta).map(([key, val]) => {
          if (typeof val === 'object' && val !== null && 'old' in val && 'new' in val) {
            return (
              <div key={key}>
                <span className="text-slate-500">{key}:</span>{' '}
                <span className="line-through text-red-400/80">{String(val.old)}</span> →{' '}
                <span className="text-emerald-400 font-semibold">{String(val.new)}</span>
              </div>
            );
          }
          return (
            <div key={key}>
              <span className="text-slate-500">{key}:</span> {String(val)}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border-l border-slate-700/80 max-w-md w-full h-full p-6 shadow-2xl text-slate-100 flex flex-col">
        <div className="flex justify-between items-center pb-4 border-b border-slate-800">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center space-x-2">
              <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Audit Trail History</span>
            </h3>
            <p className="text-xs text-slate-400">Track price changes & availability edits</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-slate-800"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="mt-4 flex-1 overflow-y-auto space-y-3 pr-1">
          {loading ? (
            <div className="flex justify-center items-center h-48 text-slate-400 text-sm">
              Loading audit logs...
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-sm">
              No audit logs recorded for this outlet yet.
            </div>
          ) : (
            logs.map((log) => (
              <div
                key={log.id}
                className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:border-slate-600 transition-colors"
              >
                <div className="flex justify-between items-start mb-1.5">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider ${formatActionBadge(
                      log.action
                    )}`}
                  >
                    {log.action.replace('_', ' ')}
                  </span>
                  <span className="text-[10px] text-slate-400">
                    {new Date(log.created_at).toLocaleString()}
                  </span>
                </div>
                <div className="text-xs text-slate-300 font-medium mt-1">
                  Actor:{' '}
                  <span className="text-amber-400 font-semibold">{log.actor_name || 'System'}</span>
                </div>
                {renderMetadata(log.metadata_json)}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
