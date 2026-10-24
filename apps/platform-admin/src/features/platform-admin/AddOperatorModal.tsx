import React, { useState, useRef } from 'react';
import { submitPlatformApprovalRequest } from '@roms/api-client';
import { Info, Loader2, CheckCircle2 } from 'lucide-react';
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
  const [userId, setUserId] = useState('');
  const [justification, setJustification] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Generate a stable idempotency key for this logical submission attempt.
  // Reused across retries of the same attempt, but refreshed after successful completion.
  const idempotencyKeyRef = useRef<string>(`op_sub_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    setError(null);
    setSuccessMessage(null);
    setIsSubmitting(true);

    try {
      if (mode === 'new') {
        if (!displayName.trim() || !email.trim()) {
          throw new Error('Please enter both full name and email address.');
        }
      } else {
        if (!userId.trim()) {
          throw new Error('Please enter the existing user UUID.');
        }
      }

      const payloadRecord =
        mode === 'new'
          ? {
              display_name: displayName.trim(),
              email: email.trim(),
            }
          : {
              target_user_id: userId.trim(),
            };

      await submitPlatformApprovalRequest(token, {
        request_type: 'operator_creation',
        target_entity_type: 'operator',
        target_entity_id: mode === 'existing' ? userId.trim() : undefined,
        payload: payloadRecord,
        justification: justification.trim() || undefined,
        idempotency_key: idempotencyKeyRef.current,
      });

      setSuccessMessage(
        'Approval request submitted successfully. Once approved, the operator will be provisioned.'
      );
      // Reset idempotency key for any future submission
      idempotencyKeyRef.current = `op_sub_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
      onSuccess();
      setTimeout(() => {
        onClose();
        setSuccessMessage(null);
      }, 1500);
    } catch (err: any) {
      setError(err.message || 'Failed to submit operator creation approval request.');
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
      title="Request Platform Operator"
      subtitle="Submit an approval request to provision or assign the Operator role."
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

        {successMessage && (
          <div
            role="status"
            className="flex items-center gap-2 rounded-md border border-ops-border bg-ops-status-positive-bg p-3 text-xs text-ops-status-positive-text"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{successMessage}</span>
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
                id="add-operator-name"
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
                id="add-operator-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@roms.com"
                className={opsInputClass}
              />
            </FormField>

            <div className="flex items-start gap-2 rounded-md border border-ops-border bg-ops-canvas p-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-ops-text-secondary" aria-hidden="true" />
              <p className="text-xs leading-5 text-ops-text-secondary">
                Upon approval, a secure temporary password will be generated automatically and delivered to the local credentials artifact. No plaintext passwords are sent or stored.
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
              id="add-operator-user-id"
              type="text"
              required
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="e.g. 35b83c12-bc5a-41aa-887b-50cce040caff"
              className={`${opsInputClass} font-mono`}
            />
          </FormField>
        )}

        <FormField id="add-operator-justification" label="Business Justification (Optional)">
          <textarea
            id="add-operator-justification"
            rows={2}
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            placeholder="e.g. Needs access to manage live orders and table maps."
            className={opsInputClass}
          />
        </FormField>

        <div className="flex items-center justify-end gap-2 border-t border-ops-border pt-4">
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                <span>Submitting...</span>
              </>
            ) : (
              <span>Submit for Approval</span>
            )}
          </Button>
        </div>
      </form>
    </Drawer>
  );
};
