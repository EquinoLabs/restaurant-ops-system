import React, { useState } from 'react';
import { PlatformOperatorCreatePayload } from '@roms/shared-types';
import { createPlatformOperator } from '@roms/api-client';
import { Eye, EyeOff, Info, Loader2 } from 'lucide-react';
import { Button, Drawer, FormField, opsInputClass } from '../../components/ops-ui';

interface AddOperatorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  token: string | null;
}

export const AddOperatorModal: React.FC<AddOperatorModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  token,
}) => {
  const [mode, setMode] = useState<'new' | 'existing'>('new');
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [userId, setUserId] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    setError(null);
    setIsSubmitting(true);

    try {
      const payload: PlatformOperatorCreatePayload =
        mode === 'new'
          ? {
              display_name: displayName.trim(),
              email: email.trim(),
              password: password,
            }
          : {
              user_id: userId.trim(),
            };

      if (mode === 'new') {
        if (!displayName.trim() || !email.trim() || !password) {
          throw new Error('Please fill all required fields for new operator account.');
        }
        if (password.length < 8) {
          throw new Error('Password must be at least 8 characters long.');
        }
      } else {
        if (!userId.trim()) {
          throw new Error('Please enter the existing user UUID.');
        }
      }

      await createPlatformOperator(payload, token);
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to create or assign operator.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const modeButtonClasses = (active: boolean) =>
    `flex-1 rounded-md px-2 py-1.5 text-xs font-semibold transition-colors ${
      active
        ? 'border border-ops-border bg-white text-ops-accent'
        : 'border border-transparent text-ops-text-secondary hover:text-ops-text-primary'
    }`;

  return (
    <Drawer
      open={isOpen}
      onClose={onClose}
      title="Add Platform Operator"
      subtitle="Grant platform access with the Operator role."
      width="w-[420px]"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div
            role="alert"
            className="rounded-md border border-ops-border bg-ops-status-critical-bg p-3 text-xs text-ops-status-critical-text"
          >
            {error}
          </div>
        )}

        {/* Mode switcher */}
        <div className="flex rounded-md bg-ops-canvas p-1">
          <button
            type="button"
            onClick={() => {
              setMode('new');
              setError(null);
            }}
            className={modeButtonClasses(mode === 'new')}
          >
            New Account
          </button>
          <button
            type="button"
            onClick={() => {
              setMode('existing');
              setError(null);
            }}
            className={modeButtonClasses(mode === 'existing')}
          >
            Promote Existing User
          </button>
        </div>

        {mode === 'new' ? (
          <>
            <FormField id="add-operator-name" label="Full Name / Display Name" required>
              <input
                type="text"
                required
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. Operations Assistant"
                className={opsInputClass}
              />
            </FormField>

            <FormField id="add-operator-email" label="Email Address" required>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@roms.com"
                className={opsInputClass}
              />
            </FormField>

            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="add-operator-password"
                className="text-xs font-semibold text-ops-text-secondary"
              >
                Initial Password<span className="ml-0.5 text-ops-error">*</span>
              </label>
              <div className="relative">
                <input
                  id="add-operator-password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  className={`${opsInputClass} pr-9`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label="Toggle password visibility"
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-ops-text-secondary hover:text-ops-text-primary"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            </div>

            <div className="flex items-start gap-2 rounded-md border border-ops-border bg-ops-canvas p-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-ops-text-secondary" aria-hidden="true" />
              <p className="text-xs leading-5 text-ops-text-secondary">
                This account will be provisioned with standard operator permissions across
                designated restaurant nodes.
              </p>
            </div>
          </>
        ) : (
          <FormField
            id="add-operator-user-id"
            label="Existing User UUID"
            required
            hint="Assigns Platform Operator role to an active user without altering their account credentials."
          >
            <input
              type="text"
              required
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="e.g. 35b83c12-bc5a-41aa-887b-50cce040caff"
              className={`${opsInputClass} font-mono`}
            />
          </FormField>
        )}

        <div className="flex items-center justify-end gap-2 border-t border-ops-border pt-4">
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                <span>Creating...</span>
              </>
            ) : (
              <span>Confirm &amp; Add Operator</span>
            )}
          </Button>
        </div>
      </form>
    </Drawer>
  );
};
