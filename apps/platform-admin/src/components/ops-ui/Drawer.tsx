import React, { useId, useRef } from 'react';
import { X } from 'lucide-react';
import { useDialogFocus } from './useDialogFocus';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  footer?: React.ReactNode;
  width?: string;
  closeAriaLabel?: string;
  children: React.ReactNode;
  className?: string;
}

export const Drawer: React.FC<DrawerProps> = ({
  open,
  onClose,
  title,
  subtitle,
  footer,
  width = 'w-[460px]',
  closeAriaLabel = 'Close',
  children,
  className = '',
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useDialogFocus({
    open,
    onClose,
    dialogRef,
  });

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-[rgba(31,41,51,0.40)]"
        aria-hidden="true"
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={`fixed inset-y-0 right-0 z-50 flex max-w-full flex-col border-l border-ops-border bg-white shadow-ops-l2 ${width} ${className}`}
      >
        <div className="flex items-start justify-between border-b border-ops-border p-5 select-none">
          <div className="min-w-0">
            <h2
              id={titleId}
              className="text-base font-semibold leading-6 text-ops-text-primary"
            >
              {title}
            </h2>
            {subtitle && (
              <p className="mt-0.5 text-xs leading-4 text-ops-text-secondary">{subtitle}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={closeAriaLabel}
            className="ml-3 rounded p-1 text-ops-text-secondary transition-colors hover:bg-ops-canvas hover:text-ops-text-primary focus:outline-none focus:ring-2 focus:ring-ops-accent-focus"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 space-y-5 overflow-y-auto p-5 text-[13px] leading-5 text-ops-text-primary">
          {children}
        </div>
        {footer && (
          <div className="flex items-center justify-between gap-2 border-t border-ops-border bg-ops-canvas p-4 select-none">
            {footer}
          </div>
        )}
      </div>
    </>
  );
};
