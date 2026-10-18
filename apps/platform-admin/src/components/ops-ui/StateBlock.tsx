import React from 'react';
import {
  AlertTriangle,
  Ban,
  Inbox,
  Loader2,
  Lock,
  RefreshCw,
  SearchX,
  XCircle,
} from 'lucide-react';
import { Button } from './Button';

export type StateBlockVariant =
  | 'loading'
  | 'empty'
  | 'no-results'
  | 'error'
  | 'permission-denied'
  | 'not-found'
  | 'conflict'
  | 'unknown-outcome';

export interface StateBlockProps {
  variant: StateBlockVariant;
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryAction?: React.ReactNode;
  className?: string;
}

const defaults: Record<
  StateBlockVariant,
  { title: string; description?: string; Icon: React.ComponentType<{ className?: string }> }
> = {
  loading: {
    title: 'Loading…',
    description: 'Fetching the latest data.',
    Icon: Loader2,
  },
  empty: {
    title: 'Nothing here yet',
    description: 'There is no data to display.',
    Icon: Inbox,
  },
  'no-results': {
    title: 'No results match your filters',
    description: 'Try adjusting your search keywords or clear current filters.',
    Icon: SearchX,
  },
  error: {
    title: 'Something went wrong',
    description: 'We could not load this data. Try again.',
    Icon: XCircle,
  },
  'permission-denied': {
    title: "You don't have access to this page",
    description: 'Your role does not have sufficient permissions. Contact the Platform Owner to request access.',
    Icon: Lock,
  },
  'not-found': {
    title: 'Record not found',
    description: 'This record does not exist or has been removed.',
    Icon: Ban,
  },
  conflict: {
    title: 'This record changed',
    description: 'Reload to see the latest.',
    Icon: AlertTriangle,
  },
  'unknown-outcome': {
    title: 'Checking current state…',
    description: 'Verifying whether the last action completed.',
    Icon: Loader2,
  },
};

export const StateBlock: React.FC<StateBlockProps> = ({
  variant,
  title,
  description,
  actionLabel,
  onAction,
  secondaryAction,
  className = '',
}) => {
  const d = defaults[variant];
  const Icon = d.Icon;
  const resolvedTitle = title ?? d.title;
  const resolvedDescription = description ?? d.description;
  const isLoadingLike = variant === 'loading' || variant === 'unknown-outcome';

  return (
    <div
      role={variant === 'error' || variant === 'permission-denied' ? 'alert' : 'status'}
      data-state-variant={variant}
      className={`flex min-h-[60vh] flex-col items-center justify-center p-8 ${className}`}
    >
      <div className="flex w-full max-w-md flex-col items-center rounded-md border border-ops-border bg-white p-8 text-center shadow-none">
        <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-ops-canvas text-ops-text-secondary">
          <Icon
            className={`h-5 w-5 ${isLoadingLike ? 'animate-spin motion-reduce:animate-none' : ''}`}
            aria-hidden="true"
          />
        </div>
        <h2 className="text-lg font-semibold leading-tight tracking-tight text-ops-text-primary">
          {resolvedTitle}
        </h2>
        {resolvedDescription && (
          <p className="mt-2 text-sm leading-relaxed text-ops-text-secondary">
            {resolvedDescription}
          </p>
        )}
        <div className="mt-6 flex items-center justify-center gap-2">
          {variant === 'no-results' && onAction && (
            <Button variant="secondary" onClick={onAction}>
              {actionLabel ?? 'Clear filters'}
            </Button>
          )}
          {variant === 'error' && onAction && (
            <Button variant="secondary" onClick={onAction}>
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              {actionLabel ?? 'Retry'}
            </Button>
          )}
          {variant === 'conflict' && onAction && (
            <Button variant="secondary" onClick={onAction}>
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              {actionLabel ?? 'Reload'}
            </Button>
          )}
          {(variant === 'empty' ||
            variant === 'permission-denied' ||
            variant === 'not-found') &&
            onAction && (
              <Button variant="secondary" onClick={onAction}>
                {actionLabel ?? 'Back'}
              </Button>
            )}
          {secondaryAction}
        </div>
      </div>
    </div>
  );
};

export interface InlineStateBannerProps {
  variant: 'conflict' | 'unknown-outcome' | 'error';
  message: string;
  action?: React.ReactNode;
  className?: string;
}

const inlineIcons: Record<
  InlineStateBannerProps['variant'],
  React.ComponentType<{ className?: string }>
> = {
  conflict: AlertTriangle,
  'unknown-outcome': Loader2,
  error: XCircle,
};

export const InlineStateBanner: React.FC<InlineStateBannerProps> = ({
  variant,
  message,
  action,
  className = '',
}) => {
  const Icon = inlineIcons[variant];
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      data-inline-state={variant}
      className={`flex items-center justify-between gap-3 rounded-md border border-ops-border bg-ops-canvas p-3 text-[13px] font-medium text-ops-text-primary ${className}`}
    >
      <div className="flex items-center gap-2.5">
        <Icon
          className={`h-4 w-4 shrink-0 text-ops-text-secondary ${
            variant === 'unknown-outcome' ? 'animate-spin motion-reduce:animate-none text-ops-accent' : ''
          }`}
          aria-hidden="true"
        />
        <span>{message}</span>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
};

export interface SkeletonTableProps {
  rows?: number;
  className?: string;
}

export const SkeletonTable: React.FC<SkeletonTableProps> = ({ rows = 5, className = '' }) => (
  <div
    data-testid="skeleton-table"
    className={`overflow-hidden rounded-md border border-ops-border bg-white ${className}`}
    aria-hidden="true"
  >
    <div className="h-9 border-b border-ops-border bg-ops-canvas" />
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="h-10 border-b border-ops-border bg-white last:border-b-0" />
    ))}
  </div>
);
