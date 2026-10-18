import React, { useEffect, useId, useRef, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { Button } from './Button';
import { useDialogFocus } from './useDialogFocus';

export interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  consequence: string;
  confirmLabel: string;
  confirmationName: string;
  confirmationPrompt?: string;
  confirmationPlaceholder?: string;
  isSubmitting?: boolean;
  errorMessage?: string | null;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  onClose,
  onConfirm,
  title,
  consequence,
  confirmLabel,
  confirmationName,
  confirmationPrompt,
  confirmationPlaceholder,
  isSubmitting = false,
  errorMessage = null,
}) => {
  const [typed, setTyped] = useState('');
  const dialogRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (open) setTyped('');
  }, [open]);

  useDialogFocus({
    open,
    onClose,
    dialogRef,
    initialFocusRef: inputRef,
    closeOnEscape: () => !isSubmitting,
  });

  if (!open) return null;

  const canConfirm = typed.trim() === confirmationName && !isSubmitting;

  return (
    <>
      <div
        className="fixed inset-0 z-50 bg-[rgba(31,41,51,0.40)] animate-ops-fade-in motion-reduce:animate-none"
        aria-hidden="true"
      />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          ref={dialogRef}
          role="alertdialog"
          aria-modal="true"
          aria-labelledby={titleId}
          tabIndex={-1}
          className="flex max-h-full w-full max-w-[480px] flex-col rounded-md border border-ops-border bg-white shadow-ops-l2 animate-ops-dialog-enter motion-reduce:animate-none"
        >
          <div className="flex items-center justify-between border-b border-ops-border p-5">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-ops-error" aria-hidden="true" />
              <h2
                id={titleId}
                className="text-base font-semibold leading-6 text-ops-text-primary"
              >
                {title}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              disabled={isSubmitting}
              className="rounded p-1 text-ops-text-secondary transition-colors hover:bg-ops-canvas hover:text-ops-text-primary focus:outline-none focus:ring-2 focus:ring-ops-accent-focus disabled:opacity-50"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex flex-col gap-3 p-5 text-[13px] leading-5 text-ops-text-primary">
            <p>{consequence}</p>

            {errorMessage && (
              <div
                role="alert"
                className="rounded-md border border-ops-status-critical-bg bg-ops-status-critical-bg/40 p-3 text-ops-error"
              >
                {errorMessage}
              </div>
            )}

            <div className="flex flex-col gap-1.5 pt-1">
              <label
                htmlFor="confirm-dialog-typed-name"
                className="text-xs font-medium text-ops-text-secondary"
              >
                {confirmationPrompt || `To confirm, type: ${confirmationName}`}
              </label>
              <input
                id="confirm-dialog-typed-name"
                ref={inputRef}
                type="text"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder={confirmationPlaceholder || confirmationName}
                disabled={isSubmitting}
                aria-invalid={errorMessage ? true : undefined}
                className="h-8 w-full rounded-md border border-ops-border bg-white px-3 text-[13px] text-ops-text-primary placeholder:text-ops-text-disabled focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus disabled:opacity-50"
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 border-t border-ops-border bg-ops-canvas p-4">
            <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => void onConfirm()}
              disabled={!canConfirm}
            >
              {isSubmitting ? 'Working…' : confirmLabel}
            </Button>
          </div>
        </div>
      </div>
    </>
  );
};
