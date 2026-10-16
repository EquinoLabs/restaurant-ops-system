import React, { useEffect, useRef } from 'react';

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (el) => {
      if (el.hasAttribute('disabled')) return false;
      if (el.getAttribute('aria-hidden') === 'true') return false;
      if (el.closest('[hidden]')) return false;
      return true;
    }
  );
}

function trapTabKey(event: KeyboardEvent, container: HTMLElement): void {
  if (event.key !== 'Tab') return;

  const focusable = getFocusableElements(container);
  if (focusable.length === 0) {
    event.preventDefault();
    container.focus();
    return;
  }

  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const active = document.activeElement as HTMLElement | null;
  const activeInside = active ? container.contains(active) : false;

  if (event.shiftKey) {
    if (!activeInside || active === first || active === container) {
      event.preventDefault();
      last.focus();
    }
    return;
  }

  if (!activeInside || active === last) {
    event.preventDefault();
    first.focus();
  }
}

export interface DialogFocusOptions {
  open: boolean;
  onClose: () => void;
  dialogRef: React.RefObject<HTMLElement>;
  /** When false (or a predicate returns false), Escape does not close. */
  closeOnEscape?: boolean | (() => boolean);
  /** Optional element to focus first; otherwise the first focusable inside the dialog. */
  initialFocusRef?: React.RefObject<HTMLElement>;
}

/**
 * Lightweight dialog focus lifecycle: restore previous focus on open→close,
 * move focus into the dialog, and contain Tab while open. No external deps.
 */
export function useDialogFocus({
  open,
  onClose,
  dialogRef,
  closeOnEscape = true,
  initialFocusRef,
}: DialogFocusOptions): void {
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const closeOnEscapeRef = useRef(closeOnEscape);
  closeOnEscapeRef.current = closeOnEscape;

  useEffect(() => {
    if (!open) return;

    previouslyFocusedRef.current = (document.activeElement as HTMLElement | null) ?? null;

    const focusIntoDialog = () => {
      const dialog = dialogRef.current;
      if (!dialog) return;
      if (initialFocusRef?.current) {
        initialFocusRef.current.focus();
        return;
      }
      const focusable = getFocusableElements(dialog);
      if (focusable.length > 0) {
        focusable[0].focus();
        return;
      }
      dialog.focus();
    };

    const focusTimer = window.setTimeout(focusIntoDialog, 0);

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        const option = closeOnEscapeRef.current;
        const canClose = typeof option === 'function' ? option() : option;
        if (!canClose) return;
        event.preventDefault();
        onClose();
        return;
      }

      const dialog = dialogRef.current;
      if (dialog) trapTabKey(event, dialog);
    };

    document.addEventListener('keydown', onKeyDown);

    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', onKeyDown);
      const previous = previouslyFocusedRef.current;
      if (previous && previous.isConnected && typeof previous.focus === 'function') {
        previous.focus();
      }
    };
  }, [open, onClose, dialogRef, initialFocusRef]);
}
