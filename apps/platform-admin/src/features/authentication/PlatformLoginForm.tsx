import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import { AlertCircle, Eye, EyeOff, History, Loader2, ReceiptText, Store, Users } from 'lucide-react';

const scopeItems = [
  { icon: Store, text: 'Manage restaurant businesses and their outlets' },
  { icon: ReceiptText, text: 'Review subscriptions, plans and outlet limits' },
  { icon: Users, text: 'Manage platform team access' },
  { icon: History, text: 'Review the audit log of administrative actions' },
];

export const PlatformLoginForm: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);
  const pendingPasswordFocus = useRef(false);
  const { login, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (pendingPasswordFocus.current && !isSubmitting) {
      pendingPasswordFocus.current = false;
      passwordRef.current?.focus();
    }
  }, [isSubmitting, error]);

  const failSignIn = (message: string) => {
    setError(message);
    setPassword('');
    pendingPasswordFocus.current = true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
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
        failSignIn('Access Denied: Account does not have platform administrator privileges.');
        return;
      }
      navigate('/platform');
    } catch (err: any) {
      failSignIn(err.message || 'Login failed. Please check credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputClasses =
    'h-8 w-full rounded-md border border-ops-border bg-white px-2.5 text-[13px] text-ops-text-primary placeholder:text-ops-text-secondary focus:border-ops-accent focus:outline-none focus:ring-2 focus:ring-ops-accent-focus transition-colors disabled:cursor-not-allowed disabled:bg-ops-canvas disabled:text-ops-text-disabled disabled:placeholder:text-ops-text-disabled';

  return (
    <div className="flex min-h-screen items-center justify-center bg-ops-canvas p-4 md:p-6">
      <div className="flex min-h-[520px] w-full max-w-[880px] flex-col overflow-hidden rounded-md border border-ops-border bg-white shadow-ops-l2 md:flex-row">
        {/* Left section */}
        <div className="flex flex-col justify-between border-b border-ops-border bg-ops-canvas p-6 select-none md:w-[42%] md:border-b-0 md:border-r md:p-10">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[16px] font-bold tracking-tight text-ops-text-primary">
                ROMS
              </span>
              <span className="rounded-[4px] bg-ops-border px-1.5 py-0.5 text-[11px] font-medium uppercase leading-none text-ops-text-secondary">
                ADMIN
              </span>
            </div>
            <h1 className="mb-2 mt-6 text-[20px] font-semibold leading-7 tracking-tight text-ops-text-primary">
              ROMS Platform Console
            </h1>
            <p className="mb-6 text-sm leading-relaxed text-ops-text-secondary">
              The internal control panel for the ROMS restaurant ordering and operations
              platform.
            </p>

            <div className="mb-3 hidden text-[12px] font-semibold uppercase tracking-wider text-ops-text-secondary md:block">
              What you can do here
            </div>
            <ul className="hidden space-y-2.5 md:block">
              {scopeItems.map(({ icon: Icon, text }) => (
                <li
                  key={text}
                  className="flex items-start gap-2.5 text-[13px] leading-[18px] text-ops-text-primary"
                >
                  <Icon
                    className="mt-0.5 h-4 w-4 shrink-0 text-ops-text-secondary"
                    strokeWidth={1.5}
                    aria-hidden="true"
                  />
                  <span>{text}</span>
                </li>
              ))}
            </ul>
          </div>

          <p className="hidden text-xs text-ops-text-secondary md:block">
            Authorised ROMS team members only.
          </p>
        </div>

        {/* Right section */}
        <div className="flex flex-col justify-center bg-white p-6 md:w-[58%] md:p-10">
          <div className="mx-auto w-full max-w-[340px]">
            <h2 className="mb-1 text-[20px] font-semibold text-ops-text-primary">Sign in</h2>
            <p className="mb-4 text-sm text-ops-text-secondary">Use your ROMS team account.</p>

            {error && (
              <div
                role="alert"
                className="mb-4 flex items-center gap-2 rounded-md bg-ops-status-critical-bg px-3 py-2 text-[13px] font-medium text-ops-status-critical-text"
              >
                <AlertCircle className="h-4 w-4 shrink-0" strokeWidth={1.5} aria-hidden="true" />
                <span>{error}</span>
              </div>
            )}

            <form className="flex flex-col" onSubmit={handleSubmit} noValidate={false}>
              <label
                htmlFor="login-email"
                className="mb-1.5 block text-[13px] font-medium text-ops-text-primary"
              >
                Email
              </label>
              <input
                id="login-email"
                name="email"
                type="email"
                required
                autoComplete="username"
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                disabled={isSubmitting}
                className={`${inputClasses} mb-4`}
              />

              <label
                htmlFor="login-password"
                className="mb-1.5 block text-[13px] font-medium text-ops-text-primary"
              >
                Password
              </label>
              <div className="relative mb-6 flex items-center">
                <input
                  id="login-password"
                  name="password"
                  ref={passwordRef}
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isSubmitting}
                  className={`${inputClasses} pr-9`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label="Toggle password visibility"
                  className="absolute right-2 flex items-center justify-center p-0.5 text-ops-text-secondary transition-colors hover:text-ops-text-primary focus:outline-none"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                  ) : (
                    <Eye className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                  )}
                </button>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="flex h-8 w-full items-center justify-center gap-2 rounded-md bg-ops-accent text-[13px] font-medium text-white transition-colors hover:bg-ops-accent-hover active:bg-ops-accent-active focus:outline-none focus:ring-2 focus:ring-ops-accent-focus focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-80"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} aria-hidden="true" />
                    <span>Signing in…</span>
                  </>
                ) : (
                  'Sign in'
                )}
              </button>
            </form>

            <p className="mt-4 text-center text-xs text-ops-text-secondary">
              Need access? Contact the Platform Owner.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PlatformLoginForm;
