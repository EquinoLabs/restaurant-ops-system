import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Button } from '../ops-ui';

export const NotFoundPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const handleGoBack = () => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate('/platform/dashboard');
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-ops-canvas p-4 antialiased">
      <div className="flex w-full max-w-[560px] flex-col items-center">
        {/* Plain text wordmark */}
        <div className="mb-6 flex select-none items-center gap-2">
          <span className="text-[15px] font-bold uppercase tracking-tight text-ops-text-primary">
            ROMS
          </span>
          <span className="rounded-[4px] bg-ops-border px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-ops-text-secondary">
            ADMIN
          </span>
        </div>

        {/* Error card */}
        <div className="w-full rounded-md border border-ops-border bg-white p-8 sm:p-10">
          <div className="mb-2 text-[12px] font-semibold uppercase tracking-[0.05em] text-ops-text-secondary">
            ERROR 404
          </div>
          <h1 className="mb-2 text-[20px] font-semibold leading-7 tracking-tight text-ops-text-primary">
            Page not found
          </h1>
          <p className="mb-5 text-sm leading-relaxed text-ops-text-secondary">
            The page you're looking for doesn't exist or has moved.
          </p>

          <div className="mb-6 flex items-center gap-2.5 overflow-hidden rounded-md border border-ops-border bg-ops-canvas p-3 text-[13px]">
            <span className="shrink-0 select-none font-mono text-ops-text-secondary">
              Requested path:
            </span>
            <span
              title={location.pathname}
              className="truncate font-medium text-ops-text-primary"
            >
              {location.pathname}
            </span>
          </div>

          <div className="flex items-center gap-3 pt-1">
            <Link
              to="/platform/dashboard"
              className="inline-flex h-8 items-center justify-center rounded-md bg-ops-accent px-4 text-[13px] font-medium text-white transition-colors hover:bg-ops-accent-hover focus:outline-none focus:ring-2 focus:ring-ops-accent-focus focus:ring-offset-1"
            >
              Back to Overview
            </Link>
            <Button variant="secondary" className="px-4" onClick={handleGoBack}>
              Go back
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NotFoundPage;
