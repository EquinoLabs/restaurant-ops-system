import React from 'react';
import { ChevronRight, Plus } from 'lucide-react';
import { PlatformBusiness, PlatformAuditLogItem } from '@roms/shared-types';
import { PlatformTab } from './PlatformShell';
import {
  Button,
  InlineStateBanner,
  PageHeader,
  StatBlock,
  StateBlock,
  StatusBadge,
  type StatusTone,
} from '../../components/ops-ui';

export interface DashboardOverviewProps {
  businesses: PlatformBusiness[];
  recentAuditLogs?: PlatformAuditLogItem[];
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  onNavigateTab?: (tab: PlatformTab) => void;
  onOpenProvisionModal?: () => void;
  onOpenBusiness?: (businessId: string) => void;
  referenceDate?: Date;
}

export function calculateDashboardMetrics(businesses: PlatformBusiness[], referenceDate: Date = new Date()) {
  const totalBusinesses = businesses.length;
  const totalOutlets = businesses.reduce((sum, b) => sum + (b.outlets?.length || 0), 0);
  const businessesInTrial = businesses.filter((b) => b.subscription_status === 'trial').length;

  const nowMs = referenceDate.getTime();
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;

  const upcomingExpirations = businesses.filter((b) => {
    if (b.subscription_status !== 'trial' || !b.trial_ends_at) return false;
    const trialEndMs = new Date(b.trial_ends_at).getTime();
    if (isNaN(trialEndMs)) return false;
    return trialEndMs >= nowMs && trialEndMs <= nowMs + sevenDaysMs;
  }).length;

  const pastDueSubscriptions = businesses.filter((b) => b.subscription_status === 'past_due').length;

  const activeAccountCount = businesses.filter((b) => b.status === 'active').length;
  const suspendedAccountCount = businesses.filter((b) => b.status === 'suspended').length;

  return {
    totalBusinesses,
    totalOutlets,
    businessesInTrial,
    upcomingExpirations,
    pastDueSubscriptions,
    activeAccountCount,
    suspendedAccountCount,
  };
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const day = date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
  const time = date.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
  });
  return `${day}, ${time}`;
}

function humanizeAction(action: string): string {
  const words = action.replace(/_/g, ' ').toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

interface AttentionItem {
  business: PlatformBusiness;
  text: string;
  tone: StatusTone;
  badgeLabel: string;
}

function buildAttentionItems(businesses: PlatformBusiness[], referenceDate: Date): AttentionItem[] {
  const nowMs = referenceDate.getTime();
  const dayMs = 24 * 60 * 60 * 1000;
  const items: AttentionItem[] = [];

  for (const business of businesses) {
    if (business.status === 'suspended') {
      items.push({
        business,
        text: `${business.name} account is suspended`,
        tone: 'critical',
        badgeLabel: 'Suspended',
      });
      continue;
    }
    if (business.subscription_status === 'past_due') {
      items.push({
        business,
        text: `${business.name} subscription is past due`,
        tone: 'pending',
        badgeLabel: 'Past due',
      });
      continue;
    }
    if (business.subscription_status === 'trial' && business.trial_ends_at) {
      const endMs = new Date(business.trial_ends_at).getTime();
      if (isNaN(endMs)) continue;
      if (endMs < nowMs) {
        items.push({
          business,
          text: `${business.name} trial has expired`,
          tone: 'pending',
          badgeLabel: 'Trial',
        });
      } else {
        const days = Math.max(1, Math.ceil((endMs - nowMs) / dayMs));
        items.push({
          business,
          text: `${business.name} trial ends in ${days} day${days === 1 ? '' : 's'}`,
          tone: 'pending',
          badgeLabel: 'Trial',
        });
      }
    }
  }

  return items;
}

export const DashboardOverview: React.FC<DashboardOverviewProps> = ({
  businesses,
  recentAuditLogs = [],
  loading,
  error,
  onRetry,
  onNavigateTab,
  onOpenProvisionModal,
  onOpenBusiness,
  referenceDate,
}) => {
  const pageHeader = (
    <PageHeader
      title="Overview"
      description="Current state of the platform."
      action={
        onOpenProvisionModal ? (
          <Button variant="primary" onClick={onOpenProvisionModal}>
            <Plus className="h-3.5 w-3.5" aria-hidden="true" />
            Add business
          </Button>
        ) : undefined
      }
    />
  );

  if (loading && businesses.length === 0) {
    return (
      <div>
        {pageHeader}
        <StateBlock
          variant="loading"
          title="Loading platform metrics..."
          description="Fetching the latest platform data."
        />
      </div>
    );
  }

  if (error && businesses.length === 0) {
    return (
      <div>
        {pageHeader}
        <StateBlock
          variant="error"
          title="Failed to load platform data"
          description={error}
          actionLabel="Retry Loading"
          onAction={onRetry}
        />
      </div>
    );
  }

  if (businesses.length === 0) {
    return (
      <div>
        {pageHeader}
        <StateBlock
          variant="empty"
          title="No tenant businesses registered yet."
          description="Get started by provisioning your first business."
          secondaryAction={
            onOpenProvisionModal ? (
              <Button variant="primary" onClick={onOpenProvisionModal}>
                Provision Business
              </Button>
            ) : undefined
          }
        />
      </div>
    );
  }

  const metrics = calculateDashboardMetrics(businesses, referenceDate);
  const activeSubscriptions = businesses.filter(
    (b) => b.subscription_status === 'active'
  ).length;
  const attentionItems = buildAttentionItems(businesses, referenceDate ?? new Date());
  const auditItems = recentAuditLogs.slice(0, 6);

  return (
    <div className="space-y-6">
      {pageHeader}

      {error && (
        <InlineStateBanner
          variant="error"
          message={error}
          action={
            onRetry ? (
              <Button variant="secondary" onClick={onRetry}>
                Retry
              </Button>
            ) : undefined
          }
        />
      )}

      <section
        aria-label="Key platform metrics"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <StatBlock caption="Businesses" value={metrics.totalBusinesses} />
        <StatBlock caption="Outlets" value={metrics.totalOutlets} />
        <StatBlock caption="Active subscriptions" value={activeSubscriptions} />
        <StatBlock
          caption="Needs attention"
          value={attentionItems.length}
          badge={
            attentionItems.length > 0 ? (
              <StatusBadge tone="pending" label="Requires review" />
            ) : undefined
          }
        />
      </section>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
        <section className="rounded-md border border-ops-border bg-white p-5">
          <div className="flex items-center justify-between border-b border-ops-divider pb-3.5">
            <div className="flex items-center gap-2">
              <h2 className="text-[15px] leading-5 font-semibold text-ops-text-primary">
                Needs attention
              </h2>
              <StatusBadge
                tone="neutral"
                label={`${attentionItems.length} item${attentionItems.length === 1 ? '' : 's'}`}
              />
            </div>
          </div>

          {attentionItems.length === 0 ? (
            <p className="py-6 text-center text-[13px] text-ops-text-secondary">
              No businesses need attention right now.
            </p>
          ) : (
            <div className="divide-y divide-ops-divider">
              {attentionItems.map((item) => (
                <button
                  key={item.business.id}
                  type="button"
                  onClick={() => onOpenBusiness?.(item.business.id)}
                  className="group flex w-full items-center justify-between gap-3 py-3 text-left text-ops-text-primary transition-colors hover:text-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
                >
                  <span className="min-w-0 truncate text-[13px] group-hover:underline">
                    {item.text}
                  </span>
                  <span className="flex shrink-0 items-center gap-1.5">
                    <StatusBadge tone={item.tone} label={item.badgeLabel} />
                    <ChevronRight
                      className="h-4 w-4 text-ops-text-secondary transition-transform group-hover:translate-x-0.5"
                      aria-hidden="true"
                    />
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-md border border-ops-border bg-white p-5">
          <div className="flex items-center justify-between border-b border-ops-divider pb-3.5">
            <h2 className="text-[15px] leading-5 font-semibold text-ops-text-primary">
              Recent activity
            </h2>
          </div>

          {auditItems.length === 0 ? (
            <p className="py-6 text-center text-[13px] text-ops-text-secondary">
              No recent platform activity yet.
            </p>
          ) : (
            <div className="divide-y divide-ops-divider">
              {auditItems.map((log) => (
                <div key={log.id} className="flex items-start justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <p className="text-[13px] leading-5 text-ops-text-primary">
                      {humanizeAction(log.action)}
                      {log.business_name && (
                        <>
                          {' '}
                          <span className="font-medium">{log.business_name}</span>
                        </>
                      )}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-ops-text-secondary">
                      {log.actor_display_name || 'System'}
                      {log.actor_email && <> · {log.actor_email}</>}
                    </p>
                  </div>
                  <time
                    dateTime={log.created_at}
                    className="shrink-0 text-xs tabular-nums text-ops-text-secondary"
                  >
                    {formatTimestamp(log.created_at)}
                  </time>
                </div>
              ))}
            </div>
          )}

          <div className="mt-2 border-t border-ops-divider pt-3.5">
            <p className="text-xs text-ops-text-secondary">
              Showing the last {auditItems.length} event{auditItems.length === 1 ? '' : 's'}.
              Open{' '}
              {onNavigateTab ? (
                <button
                  type="button"
                  onClick={() => onNavigateTab('audit-logs')}
                  className="font-medium text-ops-accent hover:underline"
                >
                  Audit logs
                </button>
              ) : (
                <span>Audit logs</span>
              )}{' '}
              for the full history.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
};
