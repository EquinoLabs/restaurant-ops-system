import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import { Eye, EyeOff, Loader2 } from 'lucide-react';

export const PlatformLoginForm: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login, logout } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError('Please enter both email and password.');
      return;
    }

    try {
      setIsSubmitting(true);
      const userProfile = await login(email, password);
      const isPlatformUser = Boolean(userProfile.is_platform_admin || userProfile.platform_role);
      if (!isPlatformUser) {
        logout();
        setError('Access Denied: Account does not have platform administrator privileges.');
        return;
      }
      navigate('/platform');
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDemoLogin = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
  };

  const inputClasses =
    'h-9 w-full rounded-md border border-ops-border bg-white px-3 text-sm text-ops-text-primary placeholder:text-ops-text-disabled focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus transition-colors';

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-ops-canvas p-4">
      <main className="flex w-full max-w-[380px] flex-col items-center">
        {/* Sign-in card */}
        <div className="w-full rounded-md border border-ops-border bg-white p-8 shadow-sm">
          {/* Brand header */}
          <header>
            <div className="flex items-center gap-2">
              <span
                className="text-xl font-bold tracking-tight text-ops-text-primary"
                style={{ letterSpacing: '-0.5px' }}
              >
                ROMS
              </span>
              <span className="rounded bg-ops-status-neutral-bg px-1.5 py-0.5 text-[11px] font-medium uppercase text-ops-text-secondary">
                ADMIN
              </span>
            </div>
            <h1 className="mt-4 text-[18px] font-semibold leading-snug text-ops-text-primary">
              Sign in to the platform
            </h1>
            <p className="mb-6 mt-1 text-[13px] leading-relaxed text-ops-text-secondary">
              Internal operations console for ROMS team members.
            </p>
          </header>

          {/* Error alert */}
          {error && (
            <div
              role="alert"
              aria-live="polite"
              className="mb-5 rounded-md border border-ops-border bg-ops-status-critical-bg p-2.5 text-[13px] leading-snug text-ops-status-critical-text"
            >
              {error}
            </div>
          )}

          {/* Sign-in form */}
          <form className="space-y-4" onSubmit={handleSubmit} noValidate={false}>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="login-email"
                className="text-[13px] font-medium text-ops-text-primary"
              >
                Email
              </label>
              <input
                id="login-email"
                name="email"
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@roms.internal"
                className={inputClasses}
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="login-password"
                className="text-[13px] font-medium text-ops-text-primary"
              >
                Password
              </label>
              <div className="relative flex items-center">
                <input
                  id="login-password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={`${inputClasses} pr-10`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label="Toggle password visibility"
                  className="absolute right-0 flex items-center pr-3 text-ops-text-secondary hover:text-ops-text-primary focus:outline-none"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>
              </div>
              <p className="mt-1 text-xs leading-tight text-ops-text-secondary">
                Need account access? Contact Platform Owner.
              </p>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex h-9 w-full items-center justify-center rounded-md bg-ops-accent px-4 text-sm font-medium text-white transition-colors hover:bg-ops-accent-hover focus:outline-none focus:ring-2 focus:ring-ops-accent-focus focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSubmitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  'Sign in'
                )}
              </button>
            </div>
          </form>

          {/* Quick demo credentials assistant (retained existing convenience) */}
          <div className="mt-6 border-t border-ops-border pt-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-ops-text-secondary">
              Platform Admin Credentials:
            </p>
            <button
              type="button"
              onClick={() => handleDemoLogin('admin@himachalhospitality.com', 'admin123')}
              className="flex w-full items-center justify-between rounded-md border border-ops-border bg-white p-3 text-left transition-colors hover:bg-ops-canvas"
            >
              <div>
                <div className="text-xs font-semibold text-ops-accent">
                  Platform Administrator
                </div>
                <div className="text-[11px] text-ops-text-secondary">
                  admin@himachalhospitality.com
                </div>
              </div>
              <span className="rounded bg-ops-status-neutral-bg px-2 py-0.5 text-[10px] font-semibold text-ops-text-secondary">
                Select
              </span>
            </button>
          </div>
        </div>

        {/* Security footer */}
        <footer className="mt-6 text-center">
          <p className="text-xs text-ops-text-secondary">
            ROMS Platform Control Plane · Restricted access
          </p>
        </footer>
      </main>
    </div>
  );
};
