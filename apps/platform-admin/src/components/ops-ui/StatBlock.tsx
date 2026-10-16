import React from 'react';

export interface StatBlockProps {
  caption: string;
  value: string | number;
  badge?: React.ReactNode;
  className?: string;
}

export const StatBlock: React.FC<StatBlockProps> = ({ caption, value, badge, className = '' }) => (
  <div
    className={`flex min-h-24 flex-col justify-between rounded-md border border-ops-border bg-white p-4 ${className}`}
  >
    <div className="text-xs leading-4 text-ops-text-secondary">{caption}</div>
    <div className="mt-2 flex items-baseline gap-2">
      <span className="text-xl font-semibold leading-7 tabular-nums text-ops-text-primary">
        {value}
      </span>
      {badge}
    </div>
  </div>
);
