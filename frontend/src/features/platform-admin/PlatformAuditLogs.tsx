import React, { useState, useEffect, useCallback } from 'react';
import { PlatformBusiness, PlatformAuditLogItem } from '../../types/platform';
import { fetchPlatformAuditLogs } from '../../api/client';

interface PlatformAuditLogsProps {
  token: string | null;
  businesses: PlatformBusiness[];
}

export const PlatformAuditLogs: React.FC<PlatformAuditLogsProps> = ({ token, businesses }) => {
  const [logs, setLogs] = useState<PlatformAuditLogItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [limit, setLimit] = useState<number>(50);
  const [offset, setOffset] = useState<number>(0);
  const [selectedAction, setSelectedAction] = useState<string>('');
  const [selectedBusinessId, setSelectedBusinessId] = useState<string>('');

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Metadata drawer/expansion state
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);

  const loadLogs = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchPlatformAuditLogs(token, {
        limit,
        offset,
        action: selectedAction || undefined,
        business_id: selectedBusinessId || undefined,
      });
      setLogs(data.items);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message || 'Failed to load platform audit logs.');
    } finally {
      setLoading(false);
    }
  }, [token, limit, offset, selectedAction, selectedBusinessId]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  // Handle filter changes (reset offset to 0)
  const handleActionChange = (action: string) => {
    setSelectedAction(action);
    setOffset(0);
  };

  const handleBusinessChange = (bizId: string) => {
    setSelectedBusinessId(bizId);
    setOffset(0);
  };

  const handleLimitChange = (newLimit: number) => {
    setLimit(newLimit);
    setOffset(0);
  };

  const handleResetFilters = () => {
    setSelectedAction('');
    setSelectedBusinessId('');
    setOffset(0);
  };

  const toggleExpandMetadata = (id: string) => {
    setExpandedLogId((prev) => (prev === id ? null : id));
  };

  const renderActionBadge = (action: string) => {
    switch (action) {
      case 'platform.business.create':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-indigo-500/10 text-indigo-300 border border-indigo-500/30">
            Business Provisioned
          </span>
        );
      case 'platform.business.update_subscription':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-amber-500/10 text-amber-300 border border-amber-500/30">
            Subscription Updated
          </span>
        );
      case 'platform.business.suspend':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-red-500/10 text-red-400 border border-red-500/30">
            Business Suspended
          </span>
        );
      case 'platform.business.reactivate':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            Business Reactivated
          </span>
        );
      case 'platform.outlet.create':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
            Outlet Created
          </span>
        );
      case 'platform.owner.assign':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-purple-500/10 text-purple-300 border border-purple-500/30">
            Owner Assigned
          </span>
        );
      case 'platform.admin.grant':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-blue-500/10 text-blue-300 border border-blue-500/30">
            Admin Granted
          </span>
        );
      case 'platform.admin.revoke':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-rose-500/10 text-rose-400 border border-rose-500/30">
            Admin Revoked
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide bg-slate-800 text-slate-300 border border-slate-700 font-mono">
            {action}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 border border-slate-800 p-6 rounded-2xl">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <svg className="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            Platform Audit Log Viewer
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            System audit log explorer, compliance trace, and platform action audit events.
          </p>
        </div>

        <button
          onClick={loadLogs}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors flex items-center justify-center space-x-2 self-start sm:self-auto disabled:opacity-50"
        >
          <svg className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>Refresh Logs</span>
        </button>
      </div>

      {/* Filter Control Bar */}
      <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-2xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Action Filter */}
          <div>
            <label htmlFor="action-type-select" className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Action Type</label>
            <select
              id="action-type-select"
              value={selectedAction}
              onChange={(e) => handleActionChange(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">All Actions</option>
              <option value="platform.business.create">Business Provisioned</option>
              <option value="platform.business.update_subscription">Subscription Updated</option>
              <option value="platform.business.suspend">Business Suspended</option>
              <option value="platform.business.reactivate">Business Reactivated</option>
              <option value="platform.outlet.create">Outlet Created</option>
              <option value="platform.owner.assign">Owner Assigned</option>
              <option value="platform.admin.grant">Admin Access Granted</option>
              <option value="platform.admin.revoke">Admin Access Revoked</option>
            </select>
          </div>

          {/* Business Filter */}
          <div>
            <label htmlFor="business-tenant-select" className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Business Tenant</label>
            <select
              id="business-tenant-select"
              value={selectedBusinessId}
              onChange={(e) => handleBusinessChange(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 max-w-[200px]"
            >
              <option value="">All Businesses</option>
              {businesses.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>

          {/* Rows per page */}
          <div>
            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Page Size</label>
            <select
              value={limit}
              onChange={(e) => handleLimitChange(Number(e.target.value))}
              className="px-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value={10}>10 per page</option>
              <option value={25}>25 per page</option>
              <option value={50}>50 per page</option>
              <option value={100}>100 per page</option>
            </select>
          </div>
        </div>

        {(selectedAction || selectedBusinessId) && (
          <button
            onClick={handleResetFilters}
            className="px-3 py-1.5 rounded-xl text-slate-400 hover:text-white bg-slate-800/80 hover:bg-slate-800 text-xs font-medium transition-colors"
          >
            Reset Filters
          </button>
        )}
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs font-medium flex items-center justify-between">
          <div>
            <div className="font-bold">Error Loading Audit Logs</div>
            <div>{error}</div>
          </div>
          <button
            onClick={loadLogs}
            className="px-3 py-1 bg-red-500/20 hover:bg-red-500/30 text-red-300 font-semibold rounded-lg text-xs"
          >
            Retry
          </button>
        </div>
      )}

      {/* Table / List View */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        {loading ? (
          <div className="p-12 text-center text-slate-400 text-sm flex flex-col items-center space-y-3">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
            <span>Loading platform audit log events...</span>
          </div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-sm space-y-2">
            <div className="font-semibold text-slate-300">No platform audit events match the selected criteria.</div>
            <p className="text-xs text-slate-500">Try adjusting your action or business filter settings.</p>
          </div>
        ) : (
          <div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900 border-b border-slate-800 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  <tr>
                    <th className="py-3.5 px-6">Timestamp</th>
                    <th className="py-3.5 px-6">Action</th>
                    <th className="py-3.5 px-6">Actor</th>
                    <th className="py-3.5 px-6">Target Business / Outlet</th>
                    <th className="py-3.5 px-6 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {logs.map((log) => {
                    const isExpanded = expandedLogId === log.id;
                    const dateFormatted = log.created_at
                      ? new Date(log.created_at).toLocaleString(undefined, {
                          dateStyle: 'medium',
                          timeStyle: 'short',
                        })
                      : 'N/A';

                    return (
                      <React.Fragment key={log.id}>
                        <tr className="hover:bg-slate-800/40 transition-colors">
                          <td className="py-4 px-6 text-slate-400 text-[11px] whitespace-nowrap font-mono">
                            {dateFormatted}
                          </td>
                          <td className="py-4 px-6">{renderActionBadge(log.action)}</td>
                          <td className="py-4 px-6">
                            {log.actor_display_name || log.actor_email ? (
                              <div>
                                <div className="font-bold text-white">{log.actor_display_name || 'Platform Admin'}</div>
                                <div className="text-[11px] text-slate-400 font-mono">{log.actor_email}</div>
                              </div>
                            ) : (
                              <span className="text-slate-500 italic text-[11px]">System / Automated</span>
                            )}
                          </td>
                          <td className="py-4 px-6">
                            <div>
                              <div className="font-bold text-white">
                                {log.business_name || (log.business_id ? `Business (${log.business_id.slice(0, 8)}...)` : 'System Level')}
                              </div>
                              {log.outlet_name && (
                                <div className="text-[11px] text-slate-400 flex items-center gap-1">
                                  <span>Outlet:</span>
                                  <span className="text-slate-300 font-medium">{log.outlet_name}</span>
                                </div>
                              )}
                            </div>
                          </td>
                          <td className="py-4 px-6 text-right">
                            <button
                              onClick={() => toggleExpandMetadata(log.id)}
                              className="px-3 py-1 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-[11px] font-medium transition-colors"
                            >
                              {isExpanded ? 'Hide Details' : 'View Details'}
                            </button>
                          </td>
                        </tr>

                        {/* Expanded Metadata Row */}
                        {isExpanded && (
                          <tr className="bg-slate-950/80">
                            <td colSpan={5} className="p-4 border-t border-b border-slate-800/80">
                              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3 max-w-3xl mx-auto">
                                <div className="flex items-center justify-between text-xs border-b border-slate-800 pb-2">
                                  <span className="font-bold text-slate-200 uppercase tracking-wider text-[10px]">
                                    Event Identifier & Entity Trace
                                  </span>
                                  <span className="font-mono text-[10px] text-slate-500">ID: {log.id}</span>
                                </div>

                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                                  <div>
                                    <div className="text-[10px] text-slate-400 font-bold uppercase">Entity Type</div>
                                    <div className="font-mono text-slate-200 mt-0.5">{log.entity_type}</div>
                                  </div>
                                  <div>
                                    <div className="text-[10px] text-slate-400 font-bold uppercase">Entity ID</div>
                                    <div className="font-mono text-slate-200 mt-0.5 truncate">{log.entity_id}</div>
                                  </div>
                                  <div>
                                    <div className="text-[10px] text-slate-400 font-bold uppercase">Business ID</div>
                                    <div className="font-mono text-slate-200 mt-0.5 truncate">
                                      {log.business_id || 'None'}
                                    </div>
                                  </div>
                                  <div>
                                    <div className="text-[10px] text-slate-400 font-bold uppercase">Outlet ID</div>
                                    <div className="font-mono text-slate-200 mt-0.5 truncate font-mono">
                                      {log.outlet_id || 'None'}
                                    </div>
                                  </div>
                                </div>

                                <div>
                                  <div className="text-[10px] text-slate-400 font-bold uppercase mb-1">
                                    Captured Metadata Payload
                                  </div>
                                  {log.metadata_json ? (
                                    <pre className="bg-slate-950 border border-slate-800/80 p-3 rounded-xl text-slate-300 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap">
                                      {JSON.stringify(log.metadata_json, null, 2)}
                                    </pre>
                                  ) : (
                                    <div className="text-slate-500 italic text-xs">No metadata captured for this event.</div>
                                  )}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls Footer */}
            <div className="bg-slate-900 border-t border-slate-800 p-4 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-400">
              <div>
                Showing{' '}
                <span className="font-bold text-white">
                  {total === 0 ? 0 : offset + 1}
                </span>{' '}
                to{' '}
                <span className="font-bold text-white">
                  {Math.min(offset + limit, total)}
                </span>{' '}
                of <span className="font-bold text-white">{total}</span> events
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
                  disabled={offset === 0 || loading}
                  className="px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <button
                  onClick={() => setOffset((prev) => prev + limit)}
                  disabled={offset + limit >= total || loading}
                  className="px-3 py-1.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
