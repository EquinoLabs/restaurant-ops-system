import React from 'react';

export interface PageHeaderProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  action,
  className = '',
}) => (
  <div
    className={`mb-6 flex flex-col gap-2 pb-4 md:flex-row md:items-center md:justify-between ${className}`}
  >
    <div className="flex flex-col gap-1">
      <h1 className="text-xl font-semibold leading-7 tracking-tight text-ops-text-primary">
        {title}
      </h1>
      {description && (
        <p className="text-sm leading-5 text-ops-text-secondary">{description}</p>
      )}
    </div>
    {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
  </div>
);
