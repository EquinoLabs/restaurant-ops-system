import React from 'react';

export type StatusTone = 'active' | 'pending' | 'critical' | 'neutral';

export interface StatusBadgeProps {
  tone: StatusTone;
  label: string;
  className?: string;
}

const toneClasses: Record<StatusTone, string> = {
  active: 'bg-ops-status-active-bg text-ops-status-active-text',
  pending: 'bg-ops-status-pending-bg text-ops-status-pending-text',
  critical: 'bg-ops-status-critical-bg text-ops-status-critical-text',
  neutral: 'bg-ops-status-neutral-bg text-ops-status-neutral-text',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ tone, label, className = '' }) => (
  <span
    className={`inline-flex h-5 items-center rounded px-1.5 text-[11px] font-medium leading-none ${toneClasses[tone]} ${className}`}
  >
    {label}
  </span>
);
