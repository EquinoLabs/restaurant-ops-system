import React, { useState } from 'react';
import { useAuth } from '@roms/api-client';
import { PlatformBusiness, PlatformOverrideCreatePayload } from '@roms/shared-types';
import { createBusinessOverride } from '@roms/api-client';

export interface CreateOverrideModalProps {
  isOpen: boolean;
  onClose: () => void;
  business: PlatformBusiness;
  availableFeatures: Array<{ feature_code: string; feature_name: string; category: string }>;
  onSuccess: () => void;
}

export const CreateOverrideModal: React.FC<CreateOverrideModalProps> = ({
  isOpen,
  onClose,
  business,
  availableFeatures,
  onSuccess,
}) => {
  const { token } = useAuth();

  const [featureCode, setFeatureCode] = useState<string>('');
  const [overrideType, setOverrideType] = useState<'grant' | 'restrict'>('grant');
  const [outletId, setOutletId] = useState<string>('');
  const [limitValue, setLimitValue] = useState<string>('');
  const [reason, setReason] = useState<string>('');
  const [expiresAt, setExpiresAt] = useState<string>('');

  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !business.id) return;

    if (!featureCode) {
      setError('Please select a feature to override.');
      return;
    }

    const cleanReason = reason.trim();
    if (!cleanReason) {
      setError('Please provide a valid reason for this override.');
      return;
    }

    let parsedLimit: number | null = null;
    if (overrideType === 'grant' && limitValue.trim() !== '') {
      parsedLimit = parseInt(limitValue, 10);
      if (isNaN(parsedLimit) || parsedLimit < 1) {
        setError('Limit value must be a positive integer >= 1 or left blank.');
        return;
      }
    }

    let isoExpiresAt: string | null = null;
    if (expiresAt.trim() !== '') {
      const dt = new Date(expiresAt);
      if (isNaN(dt.getTime())) {
        setError('Invalid expiration date format.');
        return;
      }
      if (dt.getTime() <= Date.now()) {
        setError('Expiration timestamp must be strictly in the future.');
        return;
      }
      isoExpiresAt = dt.toISOString();
    }

    setSubmitting(true);
    setError(null);

    try {
      const payload: PlatformOverrideCreatePayload = {
        feature_code: featureCode,
        override_type: overrideType,
        outlet_id: outletId || null,
        limit_value: parsedLimit,
        reason: cleanReason,
        expires_at: isoExpiresAt,
      };

      await createBusinessOverride(token, business.id, payload);
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to issue entitlement override.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 text-slate-100">
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden p-6 space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h3 className="text-lg font-black text-white">Create Administrative Override</h3>
            <p className="text-xs text-slate-400">
              Apply a feature grant or restriction for tenant <span className="text-white font-bold">{business.name}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 text-xs font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Override Type */}
          <div>
            <label className="block text-slate-300 font-bold uppercase text-[10px] mb-1.5">Override Action</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setOverrideType('grant')}
                className={`py-2 px-3 rounded-xl border font-bold text-center transition-colors ${
                  overrideType === 'grant'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-md'
                    : 'bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700'
                }`}
              >
                GRANT Feature Access
              </button>
              <button
                type="button"
                onClick={() => setOverrideType('restrict')}
                className={`py-2 px-3 rounded-xl border font-bold text-center transition-colors ${
                  overrideType === 'restrict'
                    ? 'bg-rose-500/20 text-rose-300 border-rose-500/50 shadow-md'
                    : 'bg-slate-800 text-slate-400 border-slate-700 hover:bg-slate-700'
                }`}
              >
                RESTRICT Feature Access
              </button>
            </div>
          </div>

          {/* Feature Code Dropdown */}
          <div>
            <label className="block text-slate-300 font-bold uppercase text-[10px] mb-1">Target Feature *</label>
            <select
              value={featureCode}
              onChange={(e) => setFeatureCode(e.target.value)}
              required
              className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">-- Select Catalog Feature --</option>
              {availableFeatures.map((f) => (
                <option key={f.feature_code} value={f.feature_code}>
                  {f.feature_name} ({f.feature_code}) [{f.category}]
                </option>
              ))}
            </select>
          </div>

          {/* Target Scope */}
          <div>
            <label className="block text-slate-300 font-bold uppercase text-[10px] mb-1">Target Scope</label>
            <select
              value={outletId}
              onChange={(e) => setOutletId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">Business-Wide Scope (All Outlets)</option>
              {business.outlets?.map((o) => (
                <option key={o.id} value={o.id}>
                  Outlet: {o.name} ({o.public_slug})
                </option>
              ))}
            </select>
            <p className="text-[10px] text-slate-400 mt-1">
              Note: Outlet-scoped grants follow Decision 001 Option A replacement rules and do not increase business-wide outlet creation caps.
            </p>
          </div>

          {/* Optional Numeric Limit (For Grants) */}
          {overrideType === 'grant' && (
            <div>
              <label className="block text-slate-300 font-bold uppercase text-[10px] mb-1">
                Optional Limit Value (e.g. max outlet count)
              </label>
              <input
                type="number"
                min="1"
                placeholder="Leave blank for feature capability grant without replacing numeric cap"
                value={limitValue}
                onChange={(e) => setLimitValue(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}

          {/* Optional Expiration Datetime */}
          <div>
            <label className="block text-slate-300 font-bold uppercase text-[10px] mb-1">
              Optional Expiration Date/Time
            </label>
            <input
              type="datetime-local"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <p className="text-[10px] text-slate-400 mt-0.5">Leave blank for permanent override until manually revoked.</p>
          </div>

          {/* Reason */}
          <div>
            <label className="block text-slate-300 font-bold uppercase text-[10px] mb-1">Audit Reason *</label>
            <textarea
              rows={3}
              required
              placeholder="Provide explicit business rationale for issuing this administrative override..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-white rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 hover:bg-slate-700 font-semibold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white font-bold shadow-lg shadow-indigo-500/20 disabled:opacity-50"
            >
              {submitting ? 'Creating Override...' : 'Apply Administrative Override'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
