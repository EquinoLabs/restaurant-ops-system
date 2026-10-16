import React, { useState, useEffect, useCallback } from 'react';
import { PlatformBusiness, PlatformAuditLogItem } from '@roms/shared-types';
import { fetchPlatformAuditLogs } from '@roms/api-client';
import { Copy, Info, RefreshCw } from 'lucide-react';
import { Button, DataTable, Drawer, type DataTableColumn } from '../../components/ops-ui';

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

  // Detail drawer state
  const [selectedLog, setSelectedLog] = useState<PlatformAuditLogItem | null>(null);

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

  const handleCopyEventId = (id: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(id).catch(() => {});
    }
  };

  const formatDate = (iso: string | null | undefined): string => {
    if (!iso) return 'N/A';
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  };

  const columns: DataTableColumn<PlatformAuditLogItem>[] = [
    {
      key: 'time',
      header: 'Time',
      width: 'w-40',
      render: (log) => (
        <span className="whitespace-nowrap font-mono text-xs text-ops-text-secondary">
          {formatDate(log.created_at)}
        </span>
      ),
    },
    {
      key: 'actor',
      header: 'Actor',
      width: 'w-56',
      render: (log) =>
        log.actor_display_name || log.actor_email ? (
          <div className="min-w-0">
            <div className="truncate font-medium text-ops-text-primary">
              {log.actor_display_name || 'Platform Admin'}
            </div>
            {log.actor_email && (
              <div className="truncate font-mono text-[11px] text-ops-text-secondary">
                {log.actor_email}
              </div>
            )}
          </div>
        ) : (
          <span className="text-xs italic text-ops-text-secondary">System / Automated</span>
        ),
    },
    {
      key: 'action',
      header: 'Action',
      width: 'w-72',
      render: (log) => (
        <span className="block truncate font-mono text-xs text-ops-accent">{log.action}</span>
      ),
    },
    {
      key: 'target',
      header: 'Target',
      width: 'w-48',
      render: (log) => (
        <span className="block truncate text-ops-text-primary" title={log.outlet_name ?? log.entity_id}>
          {log.outlet_name || log.entity_id}
        </span>
      ),
    },
    {
      key: 'business',
      header: 'Business',
      width: 'w-56',
      render: (log) => (
        <span
          className="block truncate text-ops-text-secondary"
          title={
            log.business_name ||
            (log.business_id ? `Business (${log.business_id.slice(0, 8)}...)` : 'System Level')
          }
        >
          {log.business_name ||
            (log.business_id ? `Business (${log.business_id.slice(0, 8)}...)` : 'System Level')}
        </span>
      ),
    },
    {
      key: 'details',
      header: 'Details',
      align: 'right',
      width: 'w-32',
      render: (log) => (
        <Button variant="ghost" className="text-ops-accent hover:text-ops-accent-hover" onClick={() => setSelectedLog(log)}>
          View Details
        </Button>
      ),
    },
  ];

  const hasActiveFilters = Boolean(selectedAction || selectedBusinessId);

  return (
    <div>
      {/* Page header */}
      <div className="mb-4 flex flex-col gap-3 border-b border-ops-border pb-4 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold leading-7 tracking-tight text-ops-text-primary">
            Audit logs
          </h1>
          <p className="text-sm leading-5 text-ops-text-secondary">
            Record of important administrative actions and security events across the platform.
          </p>
        </div>
        <Button
          variant="ghost"
          className="text-ops-accent hover:text-ops-accent-hover"
          onClick={loadLogs}
          disabled={loading}
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`}
            aria-hidden="true"
          />
          Refresh
        </Button>
      </div>

      {/* Filter control bar */}
      <div className="mb-4 flex flex-col gap-3 rounded-md border border-ops-border bg-ops-canvas p-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label
              htmlFor="action-type-select"
              className="text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary"
            >
              Action Type
            </label>
            <select
              id="action-type-select"
              value={selectedAction}
              onChange={(e) => handleActionChange(e.target.value)}
              className="h-8 rounded-md border border-ops-border bg-white px-2.5 text-[13px] text-ops-text-primary focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
            >
              <option value="">All action types</option>
              <option value="platform.business.create">Business Provisioned</option>
              <option value="platform.business.update_subscription">Subscription Updated</option>
              <option value="platform.business.suspend">Business Suspended</option>
              <option value="platform.business.reactivate">Business Reactivated</option>
              <option value="platform.outlet.create">Outlet Created</option>
              <option value="platform.owner.assign">Owner Assigned</option>
              <option value="platform.admin.grant">Admin Access Granted</option>
              <option value="platform.admin.revoke">Admin Access Revoked</option>
              <option value="platform.operator.create">Operator Provisioned</option>
              <option value="platform.operator.revoke">Operator Revoked</option>
              <option value="platform.owner.transfer">Owner Transferred</option>
              <option value="platform.user.suspend">User Suspended</option>
              <option value="platform.user.reactivate">User Reactivated</option>
              <option value="platform.override.create">Override Granted</option>
              <option value="platform.override.revoke">Override Revoked</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="business-tenant-select"
              className="text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary"
            >
              Business Tenant
            </label>
            <select
              id="business-tenant-select"
              value={selectedBusinessId}
              onChange={(e) => handleBusinessChange(e.target.value)}
              className="h-8 max-w-[200px] rounded-md border border-ops-border bg-white px-2.5 text-[13px] text-ops-text-primary focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
            >
              <option value="">All businesses</option>
              {businesses.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="page-size-select"
              className="text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary"
            >
              Page Size
            </label>
            <select
              id="page-size-select"
              value={limit}
              onChange={(e) => handleLimitChange(Number(e.target.value))}
              className="h-8 rounded-md border border-ops-border bg-white px-2.5 text-[13px] text-ops-text-primary focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
            >
              <option value={10}>10 per page</option>
              <option value={25}>25 per page</option>
              <option value={50}>50 per page</option>
              <option value={100}>100 per page</option>
            </select>
          </div>
        </div>

        {hasActiveFilters && (
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              className="text-ops-error hover:bg-ops-status-critical-bg"
              onClick={handleResetFilters}
            >
              Reset filters
            </Button>
            <span className="text-xs text-ops-text-secondary">Showing filtered results</span>
          </div>
        )}
      </div>

      {/* Global error banner */}
      {error && (
        <div
          role="alert"
          className="mb-4 flex items-center justify-between gap-3 rounded-md border border-ops-border bg-ops-status-critical-bg p-4 text-xs text-ops-status-critical-text"
        >
          <div>
            <div className="font-semibold">Error Loading Audit Logs</div>
            <div>{error}</div>
          </div>
          <Button variant="secondary" onClick={loadLogs}>
            Retry
          </Button>
        </div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-md border border-ops-border bg-white">
        {loading ? (
          <div className="py-12 text-center text-sm text-ops-text-secondary">
            Loading platform audit log events...
          </div>
        ) : logs.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-sm font-semibold text-ops-text-primary">
              No platform audit events match the selected criteria.
            </p>
            <p className="mt-1 text-xs text-ops-text-secondary">
              Try adjusting your action or business filter settings.
            </p>
          </div>
        ) : (
          <DataTable
            columns={columns}
            rows={logs}
            rowKey={(log) => log.id}
            minWidth="960px"
            footer={
              <>
                <span>
                  Showing{' '}
                  <span className="font-medium text-ops-text-primary">
                    {total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)}
                  </span>{' '}
                  of{' '}
                  <span className="font-medium text-ops-text-primary">{total}</span> records
                </span>
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="secondary"
                    className="h-7 px-2 text-xs"
                    onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
                    disabled={offset === 0 || loading}
                  >
                    {'< Previous'}
                  </Button>
                  <Button
                    variant="secondary"
                    className="h-7 px-2 text-xs"
                    onClick={() => setOffset((prev) => prev + limit)}
                    disabled={offset + limit >= total || loading}
                  >
                    {'Next >'}
                  </Button>
                </div>
              </>
            }
          />
        )}
      </div>

      {/* Audit event detail drawer */}
      <Drawer
        open={selectedLog !== null}
        onClose={() => setSelectedLog(null)}
        title="Audit event detail"
        closeAriaLabel="Close inspector panel"
        footer={
          <div className="flex w-full items-center gap-2 text-xs text-ops-text-secondary">
            <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
            <p className="leading-tight">
              Administrative audit log recorded under standard platform compliance retention
              policies.
            </p>
          </div>
        }
      >
        {selectedLog && (
          <div className="space-y-5">
            {/* Event ID */}
            <div className="flex items-center gap-1.5 font-mono text-xs text-ops-text-secondary">
              <span>Event ID:</span>
              <span className="select-all font-medium text-ops-text-primary">
                {selectedLog.id}
              </span>
              <button
                type="button"
                onClick={() => handleCopyEventId(selectedLog.id)}
                aria-label="Copy Event ID"
                title="Copy Event ID"
                className="rounded p-1 text-ops-text-secondary hover:bg-ops-canvas hover:text-ops-text-primary"
              >
                <Copy className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>

            {/* Event metadata */}
            <div>
              <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary">
                Event Metadata
              </h3>
              <div className="flex flex-col gap-2 rounded-md border border-ops-border bg-ops-canvas p-3 text-[13px]">
                <div className="flex justify-between gap-3">
                  <span className="w-28 shrink-0 text-ops-text-secondary">Time</span>
                  <span className="text-right font-mono text-xs text-ops-text-primary">
                    {formatDate(selectedLog.created_at)}
                  </span>
                </div>
                <div className="flex justify-between gap-3 border-t border-ops-divider pt-2">
                  <span className="w-28 shrink-0 text-ops-text-secondary">Actor</span>
                  <div className="text-right">
                    {selectedLog.actor_display_name || selectedLog.actor_email ? (
                      <>
                        <span className="block font-medium text-ops-text-primary">
                          {selectedLog.actor_display_name || 'Platform Admin'}
                        </span>
                        {selectedLog.actor_email && (
                          <span className="block font-mono text-xs text-ops-text-secondary">
                            {selectedLog.actor_email}
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="text-xs italic text-ops-text-secondary">
                        System / Automated
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex justify-between gap-3 border-t border-ops-divider pt-2">
                  <span className="w-28 shrink-0 text-ops-text-secondary">Action</span>
                  <span className="rounded bg-white px-1.5 py-0.5 font-mono text-xs text-ops-accent">
                    {selectedLog.action}
                  </span>
                </div>
                <div className="flex justify-between gap-3 border-t border-ops-divider pt-2">
                  <span className="w-28 shrink-0 text-ops-text-secondary">Entity type</span>
                  <span className="font-mono text-xs text-ops-text-primary">
                    {selectedLog.entity_type}
                  </span>
                </div>
                <div className="flex justify-between gap-3 border-t border-ops-divider pt-2">
                  <span className="w-28 shrink-0 text-ops-text-secondary">Business</span>
                  <div className="text-right">
                    <span className="block font-medium text-ops-text-primary">
                      {selectedLog.business_name || 'System Level'}
                    </span>
                    {selectedLog.business_id && (
                      <span className="block font-mono text-xs text-ops-text-secondary">
                        {selectedLog.business_id}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex justify-between gap-3 border-t border-ops-divider pt-2">
                  <span className="w-28 shrink-0 text-ops-text-secondary">Outlet</span>
                  {selectedLog.outlet_name ? (
                    <span className="text-right text-ops-text-primary">
                      {selectedLog.outlet_name}
                    </span>
                  ) : (
                    <span className="text-right text-xs italic text-ops-text-secondary">
                      — (Business-level change)
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Details attribute table */}
            {selectedLog.metadata_json && Object.keys(selectedLog.metadata_json).length > 0 && (
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary">
                    Details
                  </h3>
                  <span className="text-[11px] text-ops-text-secondary">
                    {Object.keys(selectedLog.metadata_json).length} attributes
                  </span>
                </div>
                <div className="overflow-hidden rounded-md border border-ops-border">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="h-7 border-b border-ops-border bg-ops-canvas text-[11px] text-ops-text-secondary">
                        <th scope="col" className="w-1/3 px-2.5 font-semibold">
                          Field
                        </th>
                        <th scope="col" className="px-2.5 font-semibold">
                          Value
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ops-divider">
                      {Object.entries(selectedLog.metadata_json).map(([key, value]) => (
                        <tr key={key}>
                          <td className="bg-ops-canvas px-2.5 py-2 align-top font-mono text-ops-text-secondary">
                            {key}
                          </td>
                          <td className="px-2.5 py-2 font-mono text-ops-text-primary">
                            {typeof value === 'string' ? value : JSON.stringify(value)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Captured metadata payload */}
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary">
                Captured Metadata Payload
              </div>
              {selectedLog.metadata_json ? (
                <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border border-ops-border bg-ops-canvas p-3 font-mono text-[11px] text-ops-text-primary">
                  {JSON.stringify(selectedLog.metadata_json, null, 2)}
                </pre>
              ) : (
                <p className="text-xs italic text-ops-text-secondary">
                  No metadata captured for this event.
                </p>
              )}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
};
