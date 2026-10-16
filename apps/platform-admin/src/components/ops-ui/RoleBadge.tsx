import React from 'react';

export interface RoleBadgeProps {
  label: string;
  className?: string;
}

export const RoleBadge: React.FC<RoleBadgeProps> = ({ label, className = '' }) => (
  <span
    className={`inline-flex h-5 items-center rounded bg-ops-status-neutral-bg px-1.5 text-[11px] font-medium leading-none text-ops-status-neutral-text ${className}`}
  >
    {label}
  </span>
);
