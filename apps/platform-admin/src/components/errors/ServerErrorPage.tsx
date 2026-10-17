import React from 'react';
import { Button } from '../ops-ui';

export interface ServerErrorPageProps {
  error: unknown;
}

const MAX_MESSAGE_LENGTH = 500;

const extractMessage = (error: unknown): string | null => {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (typeof error === 'string' && error) {
    return error;
  }
  return null;
};

export const ServerErrorPage: React.FC<ServerErrorPageProps> = ({ error }) => {
  const rawMessage = extractMessage(error);
  const message = rawMessage
    ? rawMessage.length > MAX_MESSAGE_LENGTH
      ? `${rawMessage.slice(0, MAX_MESSAGE_LENGTH)}…`
      : rawMessage
    : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-ops-canvas p-6 antialiased">
      <div className="w-full max-w-[560px]">
        {/* Plain text wordmark */}
        <div className="mb-6 flex select-none items-center gap-2">
          <span className="text-[20px] font-bold leading-6 tracking-tight text-ops-text-primary">
            ROMS
          </span>
          <span className="rounded-[4px] bg-ops-border px-1.5 py-0.5 text-[11px] font-semibold uppercase text-ops-text-secondary">
            ADMIN
          </span>
        </div>

        {/* Error card */}
        <div className="rounded-md border border-ops-border bg-white p-9 sm:p-10">
          <p className="text-[12px] font-semibold uppercase tracking-wider text-ops-text-secondary">
            ERROR 500
          </p>
          <h1 className="mb-3 mt-1.5 text-[20px] font-semibold text-ops-text-primary">
            Something went wrong
          </h1>
          <p className="mb-5 text-sm leading-relaxed text-ops-text-secondary">
            The portal ran into an unexpected error. If you were saving a change, check its
            current state before trying again.
          </p>

          {message && (
            <details className="mb-6">
              <summary className="cursor-pointer select-none py-1 text-[12px] font-medium text-ops-text-secondary transition-colors hover:text-ops-text-primary">
                Technical details
              </summary>
              <div className="mt-2.5 whitespace-pre-wrap break-words rounded-md bg-ops-canvas p-3 font-mono text-[12px] leading-[18px] text-ops-text-primary">
                {message}
              </div>
            </details>
          )}

          <div className="mb-5 mt-6 flex flex-wrap items-center gap-3">
            <Button
              variant="primary"
              className="px-4"
              onClick={() => window.location.reload()}
            >
              Reload page
            </Button>
            <Button
              variant="secondary"
              className="px-4"
              onClick={() => window.location.assign('/platform/dashboard')}
            >
              Back to Overview
            </Button>
          </div>

          <div className="border-t border-ops-divider pt-4">
            <p className="text-xs text-ops-text-secondary">
              If this keeps happening, contact the ROMS engineering team.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ServerErrorPage;
