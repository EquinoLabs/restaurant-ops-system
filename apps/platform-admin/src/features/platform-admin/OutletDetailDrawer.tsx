import React, { useState, useEffect } from 'react';
import { PlatformBusiness, PlatformOutlet } from '@roms/shared-types';
import { EffectiveEntitlementsTab } from './EffectiveEntitlementsTab';
import { SubscriptionHistoryTab } from './SubscriptionHistoryTab';
import { useAuth } from '@roms/api-client';
import { UserMe } from '@roms/shared-types';
import { updatePlatformBusinessProfile, updatePlatformOutletProfile } from '@roms/api-client';

export interface OutletDetailDrawerProps {
  business: PlatformBusiness | null;
  isOpen: boolean;
  onClose: () => void;
  onAddOutlet?: (biz: PlatformBusiness) => void;
  onEditSubscription?: (biz: PlatformBusiness) => void;
  onAssignOwner?: (bizId: string, outlet: PlatformOutlet) => void;
  onBusinessUpdated?: (updatedBiz: PlatformBusiness) => void;
}

export const OutletDetailDrawer: React.FC<OutletDetailDrawerProps> = ({
  business,
  isOpen,
  onClose,
  onAddOutlet,
  onEditSubscription,
  onAssignOwner,
  onBusinessUpdated,
}) => {
  const [activeTab, setActiveTab] = useState<'outlets' | 'entitlements' | 'subscriptions'>('outlets');
  const [activeBusiness, setActiveBusiness] = useState<PlatformBusiness | null>(business);

  useEffect(() => {
    setActiveBusiness(business);
  }, [business]);

  // Auth context for role-based editing controls
  let currentUser: UserMe | null = null;
  let authToken: string | null = null;
  try {
    const auth = useAuth();
    currentUser = auth.user;
    authToken = auth.token;
  } catch {
    currentUser = null;
    authToken = null;
  }

  // Owners and Admins may edit Business name and Outlet profiles and view commercial data.
  // Operators are strictly read-only (Owner Decision 004) — mirrors backend
  // PATCH /api/v1/platform/outlets/{outlet_id}, which allows owner/admin only.
  const userRole = currentUser?.platform_role?.trim().toLowerCase();
  const isAuthorizedCommercial = Boolean(
    currentUser && (
      userRole === 'owner' ||
      userRole === 'admin' ||
      (!userRole && currentUser.is_platform_admin)
    )
  );
  const isCurrentOwnerOrAdmin = isAuthorizedCommercial;

  useEffect(() => {
    if (!isAuthorizedCommercial && activeTab !== 'outlets') {
      setActiveTab('outlets');
    }
  }, [isAuthorizedCommercial, activeTab]);

  // Business Name Editing State
  const [isEditingBusinessName, setIsEditingBusinessName] = useState(false);
  const [businessNameInput, setBusinessNameInput] = useState('');
  const [isSavingBusinessName, setIsSavingBusinessName] = useState(false);
  const [businessNameError, setBusinessNameError] = useState<string | null>(null);
  const [businessSuccessMessage, setBusinessSuccessMessage] = useState<string | null>(null);

  // Outlet Profile Editing State
  const [editingOutlet, setEditingOutlet] = useState<PlatformOutlet | null>(null);
  const [outletForm, setOutletForm] = useState({
    name: '',
    address: '',
    timezone: 'Asia/Kolkata',
    currency: 'INR',
    primary_color: '',
    accent_color: '',
  });
  const [isSavingOutlet, setIsSavingOutlet] = useState(false);
  const [outletFormError, setOutletFormError] = useState<string | null>(null);
  const [outletSuccessMessage, setOutletSuccessMessage] = useState<string | null>(null);

  // Close drawer on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        if (editingOutlet) {
          setEditingOutlet(null);
        } else if (isEditingBusinessName) {
          setIsEditingBusinessName(false);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, editingOutlet, isEditingBusinessName]);

  if (!isOpen || !activeBusiness) return null;

  const currentOutletCount = activeBusiness.outlets?.length || 0;
  const maxOutlets = activeBusiness.max_outlets;
  const isLimitReached = maxOutlets !== null && maxOutlets !== undefined && currentOutletCount >= maxOutlets;

  const handleSaveBusinessName = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeBusiness) return;
    if (!isCurrentOwnerOrAdmin) {
      setBusinessNameError('Permission denied: Platform Operators cannot edit business legal identity.');
      return;
    }
    const cleanName = businessNameInput.trim();
    if (!cleanName) {
      setBusinessNameError('Business name cannot be empty.');
      return;
    }
    if (cleanName.length > 200) {
      setBusinessNameError('Business name cannot exceed 200 characters.');
      return;
    }

    try {
      setIsSavingBusinessName(true);
      setBusinessNameError(null);
      const token = authToken || '';
      const updated = await updatePlatformBusinessProfile(activeBusiness.id, { name: cleanName }, token);
      const updatedBiz: PlatformBusiness = {
        ...activeBusiness,
        name: updated.name,
      };
      setActiveBusiness(updatedBiz);
      setIsEditingBusinessName(false);
      setBusinessSuccessMessage('Business name updated successfully.');
      onBusinessUpdated?.(updatedBiz);
    } catch (err: any) {
      setBusinessNameError(err.message || 'Failed to update business name.');
    } finally {
      setIsSavingBusinessName(false);
    }
  };

  const handleOpenOutletEdit = (outlet: PlatformOutlet) => {
    if (!isCurrentOwnerOrAdmin) {
      setOutletFormError('Permission denied: Platform Operators cannot edit outlet profiles.');
      return;
    }
    setEditingOutlet(outlet);
    setOutletForm({
      name: outlet.name,
      address: outlet.address || '',
      timezone: outlet.timezone || 'Asia/Kolkata',
      currency: outlet.currency || 'INR',
      primary_color: outlet.primary_color || '',
      accent_color: outlet.accent_color || '',
    });
    setOutletFormError(null);
  };

  const handleCloseOutletEdit = () => {
    if (isSavingOutlet) return;
    setEditingOutlet(null);
    setOutletFormError(null);
  };

  const handleSaveOutletProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingOutlet || !activeBusiness) return;
    if (!isCurrentOwnerOrAdmin) {
      setOutletFormError('Permission denied: Platform Operators cannot edit outlet profiles.');
      return;
    }

    const cleanName = outletForm.name.trim();
    if (!cleanName) {
      setOutletFormError('Outlet name cannot be empty.');
      return;
    }
    if (cleanName.length > 200) {
      setOutletFormError('Outlet name cannot exceed 200 characters.');
      return;
    }

    const cleanCurrency = outletForm.currency.trim().toUpperCase();
    if (cleanCurrency.length !== 3 || !/^[A-Z]{3}$/.test(cleanCurrency)) {
      setOutletFormError('Currency code must be a 3-letter ISO code (e.g. INR, USD).');
      return;
    }

    const cleanTimezone = outletForm.timezone.trim();
    if (!cleanTimezone) {
      setOutletFormError('Timezone identifier is required.');
      return;
    }

    const hexRegex = /^#[0-9a-fA-F]{6}$/;
    const cleanPrimary = outletForm.primary_color.trim();
    if (cleanPrimary && !hexRegex.test(cleanPrimary)) {
      setOutletFormError('Primary color must be in #RRGGBB format (e.g. #4F46E5).');
      return;
    }

    const cleanAccent = outletForm.accent_color.trim();
    if (cleanAccent && !hexRegex.test(cleanAccent)) {
      setOutletFormError('Accent color must be in #RRGGBB format (e.g. #10B981).');
      return;
    }

    try {
      setIsSavingOutlet(true);
      setOutletFormError(null);
      const token = authToken || '';
      const payload = {
        name: cleanName,
        address: outletForm.address.trim() || null,
        timezone: cleanTimezone,
        currency: cleanCurrency,
        primary_color: cleanPrimary ? cleanPrimary.toUpperCase() : null,
        accent_color: cleanAccent ? cleanAccent.toUpperCase() : null,
      };

      const updated = await updatePlatformOutletProfile(editingOutlet.id, payload, token);
      const updatedOutlets = activeBusiness.outlets.map((o) =>
        o.id === editingOutlet.id
          ? {
              ...o,
              name: updated.name,
              address: updated.address,
              timezone: updated.timezone,
              currency: updated.currency,
              primary_color: updated.primary_color,
              accent_color: updated.accent_color,
            }
          : o
      );
      const updatedBiz: PlatformBusiness = {
        ...activeBusiness,
        outlets: updatedOutlets,
      };
      setActiveBusiness(updatedBiz);
      setEditingOutlet(null);
      setOutletSuccessMessage(`Outlet '${cleanName}' profile updated successfully.`);
      onBusinessUpdated?.(updatedBiz);
    } catch (err: any) {
      setOutletFormError(err.message || 'Failed to update outlet profile.');
    } finally {
      setIsSavingOutlet(false);
    }
  };

  const renderSubscriptionBadge = (subStatus: string) => {
    switch (subStatus) {
      case 'active':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 uppercase">Active Sub</span>;
      case 'past_due':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 uppercase">Past Due</span>;
      case 'cancelled':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-400 border border-red-500/30 uppercase">Cancelled</span>;
      case 'trial':
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-400 border border-sky-500/30 uppercase">Trial</span>;
    }
  };

  const renderAccountBadge = (status: string) => {
    if (status === 'suspended') {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30 uppercase">Suspended</span>;
    }
    return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 uppercase">Active</span>;
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/80 backdrop-blur-sm flex justify-end">
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer Container */}
      <div className="relative w-full max-w-2xl bg-slate-900 border-l border-slate-800 shadow-2xl h-full flex flex-col z-10 text-slate-100 overflow-y-auto">
        {/* Drawer Header */}
        <div className="p-6 border-b border-slate-800 sticky top-0 bg-slate-900/95 backdrop-blur-md z-20 space-y-4">
          <div className="flex items-start justify-between">
            <div className="flex-1 pr-4">
              <div className="flex flex-wrap items-center gap-2 mb-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                  Tenant Detail Drawer
                </span>
                {renderAccountBadge(activeBusiness.status)}
                {isAuthorizedCommercial && activeBusiness.subscription_status && renderSubscriptionBadge(activeBusiness.subscription_status)}
              </div>

              {/* Business Name with Edit Form or Display */}
              {isEditingBusinessName ? (
                <form onSubmit={handleSaveBusinessName} className="mt-2 space-y-2">
                  <div className="flex items-center space-x-2">
                    <input
                      type="text"
                      value={businessNameInput}
                      onChange={(e) => setBusinessNameInput(e.target.value)}
                      disabled={isSavingBusinessName}
                      className="px-3 py-1.5 rounded-xl bg-slate-950 border border-indigo-500 text-white text-base font-bold focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      placeholder="Business legal name"
                      aria-label="Business Name Input"
                    />
                    <button
                      type="submit"
                      disabled={isSavingBusinessName}
                      className="px-3 py-1.5 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-colors disabled:opacity-50"
                    >
                      {isSavingBusinessName ? 'Saving...' : 'Save'}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setIsEditingBusinessName(false);
                        setBusinessNameError(null);
                      }}
                      disabled={isSavingBusinessName}
                      className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                  {businessNameError && (
                    <p className="text-xs text-rose-400 font-medium">{businessNameError}</p>
                  )}
                </form>
              ) : (
                <div className="flex items-center space-x-2">
                  <h2 className="text-xl font-black text-white tracking-tight">{activeBusiness.name}</h2>
                  {isCurrentOwnerOrAdmin ? (
                    <button
                      onClick={() => {
                        setBusinessNameInput(activeBusiness.name);
                        setIsEditingBusinessName(true);
                        setBusinessNameError(null);
                      }}
                      className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                      title="Edit Business Name"
                      aria-label="Edit Business Name"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                  ) : (
                    <span
                      className="text-[10px] text-slate-500 font-semibold px-2 py-0.5 rounded bg-slate-800/50 border border-slate-700/50"
                      title="Business legal name editing requires Platform Owner or Admin privileges"
                    >
                      Name locked
                    </span>
                  )}
                </div>
              )}

              {businessSuccessMessage && (
                <div className="mt-2 p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-xs flex items-center justify-between">
                  <span>{businessSuccessMessage}</span>
                  <button onClick={() => setBusinessSuccessMessage(null)} className="text-emerald-400 font-bold ml-2">✕</button>
                </div>
              )}

              <p className="text-xs text-slate-400 mt-1">
                Registered ID: <span className="font-mono text-slate-300">{activeBusiness.id}</span>
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              aria-label="Close Outlet Detail Drawer"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center space-x-2 border-b border-slate-800/80 pb-1">
            <button
              onClick={() => setActiveTab('outlets')}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-colors ${
                activeTab === 'outlets'
                  ? 'bg-indigo-500 text-white shadow-md shadow-indigo-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              Outlets & Overview
            </button>
            {isAuthorizedCommercial && (
              <button
                onClick={() => setActiveTab('entitlements')}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-colors ${
                  activeTab === 'entitlements'
                    ? 'bg-indigo-500 text-white shadow-md shadow-indigo-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                Effective Entitlements & Overrides
              </button>
            )}
            {isAuthorizedCommercial && (
              <button
                onClick={() => setActiveTab('subscriptions')}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-colors ${
                  activeTab === 'subscriptions'
                    ? 'bg-indigo-500 text-white shadow-md shadow-indigo-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                Subscription History
              </button>
            )}
          </div>
        </div>

        {/* Global Feedback for Outlets */}
        {outletSuccessMessage && (
          <div className="mx-6 mt-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-xs flex items-center justify-between">
            <span>{outletSuccessMessage}</span>
            <button onClick={() => setOutletSuccessMessage(null)} className="text-emerald-400 font-bold ml-2">✕</button>
          </div>
        )}

        {/* Drawer Content */}
        <div className="p-6 space-y-6 flex-1">
          {activeTab === 'entitlements' ? (
            <EffectiveEntitlementsTab business={activeBusiness} />
          ) : activeTab === 'subscriptions' ? (
            <SubscriptionHistoryTab
              business={activeBusiness}
              onEditSubscription={onEditSubscription}
            />
          ) : (
            <>
              {/* Tenant Business Summary Grid */}
              <div className={`bg-slate-950/60 border border-slate-800 rounded-2xl p-4 grid ${isAuthorizedCommercial ? 'grid-cols-2 sm:grid-cols-4' : 'grid-cols-1 sm:grid-cols-2'} gap-4 text-xs`}>
                {isAuthorizedCommercial && (
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Plan Tier</span>
                    <span className="font-bold text-white capitalize mt-0.5 block">
                      {activeBusiness.plan_name || 'Unassigned'}
                    </span>
                  </div>
                )}
                {isAuthorizedCommercial && (
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Outlet Capacity</span>
                    <span className="font-bold text-white mt-0.5 block">
                      {currentOutletCount} / {maxOutlets !== null && maxOutlets !== undefined ? maxOutlets : '∞'}
                    </span>
                  </div>
                )}
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-semibold">Created Date</span>
                  <span className="font-bold text-slate-300 font-mono text-[11px] mt-0.5 block">
                    {activeBusiness.created_at ? new Date(activeBusiness.created_at).toLocaleDateString() : 'N/A'}
                  </span>
                </div>
                {isAuthorizedCommercial && (
                  <div>
                    <span className="text-slate-400 block text-[10px] uppercase font-semibold">Trial Status</span>
                    <span className="font-bold text-slate-300 text-[11px] mt-0.5 block">
                      {activeBusiness.trial_ends_at ? `Expires ${new Date(activeBusiness.trial_ends_at).toLocaleDateString()}` : 'N/A'}
                    </span>
                  </div>
                )}
              </div>

              {/* Quick Actions Bar */}
              <div className="flex flex-wrap items-center gap-3 pt-2">
                {onEditSubscription && isCurrentOwnerOrAdmin && (
                  <button
                    onClick={() => onEditSubscription(activeBusiness)}
                    className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition-colors flex items-center space-x-1.5"
                  >
                    <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    <span>Edit Subscription & Status</span>
                  </button>
                )}

                {onAddOutlet && isCurrentOwnerOrAdmin && (
                  <button
                    disabled={isLimitReached}
                    onClick={() => onAddOutlet(activeBusiness)}
                    title={isLimitReached ? `Limit of ${maxOutlets} outlets reached` : 'Provision New Outlet'}
                    className={`px-3.5 py-2 rounded-xl border text-xs font-semibold transition-colors flex items-center space-x-1.5 ${
                      isLimitReached
                        ? 'bg-slate-800/40 text-slate-500 border-slate-800 cursor-not-allowed'
                        : 'bg-indigo-500 hover:bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-500/20'
                    }`}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                    </svg>
                    <span>Provision New Outlet</span>
                  </button>
                )}
              </div>

              {/* Outlets Section Header */}
              <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                    Associated Outlets ({currentOutletCount})
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Physical and digital menu branches registered under {activeBusiness.name}
                  </p>
                </div>
              </div>

              {/* Outlets List */}
              {currentOutletCount === 0 ? (
                <div className="p-10 text-center bg-slate-950/60 border border-slate-800/80 rounded-2xl text-slate-400 space-y-3">
                  <svg className="w-10 h-10 text-slate-600 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5m3 0h1m-4-8l2-2m0 0l2 2m-2-2v4" />
                  </svg>
                  <p className="text-xs font-semibold text-slate-300">No outlets registered under this business yet.</p>
                  {onAddOutlet && isCurrentOwnerOrAdmin && (
                    <button
                      onClick={() => onAddOutlet(activeBusiness)}
                      className="mt-2 px-3.5 py-1.5 rounded-xl bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-500/40 text-indigo-300 text-xs font-bold transition-colors"
                    >
                      Add Primary Outlet
                    </button>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  {activeBusiness.outlets.map((outlet) => (
                    <div
                      key={outlet.id}
                      className="bg-slate-950/80 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-3 hover:border-slate-700 transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center space-x-2">
                            <h4 className="text-sm font-bold text-white">{outlet.name}</h4>
                            <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 uppercase">
                              {outlet.status || 'Active'}
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 mt-1">
                            {outlet.address || 'No physical address listed'}
                          </p>
                        </div>
                        <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                          /m/{outlet.public_slug}
                        </span>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px] text-slate-400 pt-2 border-t border-slate-800/60">
                        <div>
                          <span className="text-slate-500 block">Currency</span>
                          <span className="font-semibold text-slate-300">{outlet.currency}</span>
                        </div>
                        <div>
                          <span className="text-slate-500 block">Timezone</span>
                          <span className="font-semibold text-slate-300">{outlet.timezone}</span>
                        </div>
                        <div>
                          <span className="text-slate-500 block">Registered</span>
                          <span className="font-semibold text-slate-300 font-mono">
                            {outlet.created_at ? new Date(outlet.created_at).toLocaleDateString() : 'N/A'}
                          </span>
                        </div>
                      </div>

                      {/* Branding color indicators if configured */}
                      {(outlet.primary_color || outlet.accent_color) && (
                        <div className="flex items-center space-x-4 text-[11px] text-slate-400 pt-1">
                          {outlet.primary_color && (
                            <span className="flex items-center space-x-1.5">
                              <span
                                className="w-3 h-3 rounded-full border border-slate-700 inline-block shrink-0 shadow-sm"
                                style={{ backgroundColor: outlet.primary_color }}
                              />
                              <span className="font-mono text-[10px] text-slate-300">Primary: {outlet.primary_color}</span>
                            </span>
                          )}
                          {outlet.accent_color && (
                            <span className="flex items-center space-x-1.5">
                              <span
                                className="w-3 h-3 rounded-full border border-slate-700 inline-block shrink-0 shadow-sm"
                                style={{ backgroundColor: outlet.accent_color }}
                              />
                              <span className="font-mono text-[10px] text-slate-300">Accent: {outlet.accent_color}</span>
                            </span>
                          )}
                        </div>
                      )}

                      <div className="pt-3 border-t border-slate-800/60 flex items-center justify-between">
                        <a
                          href={`/m/${outlet.public_slug}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-semibold text-emerald-400 hover:underline flex items-center space-x-1"
                        >
                          <span>Preview Live QR Menu</span>
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>

                        <div className="flex items-center space-x-2">
                          {/* Edit Outlet Profile button available to Owners and Admins only (Owner Decision 004) */}
                          {isCurrentOwnerOrAdmin ? (
                            <button
                              onClick={() => handleOpenOutletEdit(outlet)}
                              className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors flex items-center space-x-1"
                              aria-label={`Edit Profile for ${outlet.name}`}
                            >
                              <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                              </svg>
                              <span>Edit Profile</span>
                            </button>
                          ) : (
                            <span
                              className="text-[10px] text-slate-500 font-semibold px-2 py-0.5 rounded bg-slate-800/50 border border-slate-700/50"
                              title="Outlet profile editing requires Platform Owner or Admin privileges"
                            >
                              Profile locked
                            </span>
                          )}

                          {onAssignOwner && isCurrentOwnerOrAdmin && (
                            <button
                              onClick={() => onAssignOwner(activeBusiness.id, outlet)}
                              className="px-3 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-semibold transition-colors"
                            >
                              Assign Owner
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Edit Outlet Profile Modal */}
      {editingOutlet && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-800">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5m3 0h1m-4-8l2-2m0 0l2 2m-2-2v4" />
                  </svg>
                  Edit Outlet Profile
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">Update operational metadata and branding colors</p>
              </div>
              <button
                onClick={handleCloseOutletEdit}
                disabled={isSavingOutlet}
                className="text-slate-400 hover:text-white p-1"
                aria-label="Close Outlet Edit Modal"
              >
                ✕
              </button>
            </div>

            {outletFormError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-xs">
                {outletFormError}
              </div>
            )}

            <form onSubmit={handleSaveOutletProfile} className="space-y-4">
              {/* Outlet Name */}
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1">
                  Outlet Name <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={outletForm.name}
                  onChange={(e) => setOutletForm({ ...outletForm, name: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white text-xs focus:outline-none focus:border-indigo-500"
                  placeholder="e.g. Hilltop Branch"
                  aria-label="Outlet Name Input"
                />
              </div>

              {/* Public Slug (Immutable) */}
              <div>
                <label className="block text-xs font-bold text-slate-400 mb-1 flex items-center justify-between">
                  <span>Public Slug (Immutable)</span>
                  <span className="text-[10px] text-amber-400 font-normal">Locked to protect live QR links</span>
                </label>
                <input
                  type="text"
                  readOnly
                  disabled
                  value={editingOutlet.public_slug}
                  className="w-full px-3 py-2 bg-slate-800/40 border border-slate-800 rounded-xl text-slate-500 text-xs font-mono cursor-not-allowed select-none"
                  aria-label="Public Slug Readonly"
                />
              </div>

              {/* Address */}
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1">Physical Address</label>
                <textarea
                  rows={2}
                  value={outletForm.address}
                  onChange={(e) => setOutletForm({ ...outletForm, address: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white text-xs focus:outline-none focus:border-indigo-500"
                  placeholder="Street address, city, state, postal code"
                  aria-label="Physical Address Input"
                />
              </div>

              {/* Timezone & Currency Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1">Timezone</label>
                  <input
                    type="text"
                    required
                    value={outletForm.timezone}
                    onChange={(e) => setOutletForm({ ...outletForm, timezone: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white text-xs font-mono focus:outline-none focus:border-indigo-500"
                    placeholder="e.g. Asia/Kolkata"
                    aria-label="Timezone Input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1">Currency Code</label>
                  <input
                    type="text"
                    required
                    maxLength={3}
                    value={outletForm.currency}
                    onChange={(e) => setOutletForm({ ...outletForm, currency: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white text-xs font-mono uppercase focus:outline-none focus:border-indigo-500"
                    placeholder="e.g. INR"
                    aria-label="Currency Code Input"
                  />
                </div>
              </div>

              {/* Branding Colors Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1">Primary Color (#RRGGBB)</label>
                  <div className="flex items-center space-x-2">
                    <input
                      type="color"
                      value={outletForm.primary_color || '#4F46E5'}
                      onChange={(e) => setOutletForm({ ...outletForm, primary_color: e.target.value.toUpperCase() })}
                      className="w-8 h-8 rounded-lg bg-transparent border-0 cursor-pointer p-0 shrink-0"
                    />
                    <input
                      type="text"
                      placeholder="#4F46E5"
                      maxLength={7}
                      value={outletForm.primary_color}
                      onChange={(e) => setOutletForm({ ...outletForm, primary_color: e.target.value.toUpperCase() })}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white text-xs font-mono uppercase focus:outline-none focus:border-indigo-500"
                      aria-label="Primary Color Input"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1">Accent Color (#RRGGBB)</label>
                  <div className="flex items-center space-x-2">
                    <input
                      type="color"
                      value={outletForm.accent_color || '#10B981'}
                      onChange={(e) => setOutletForm({ ...outletForm, accent_color: e.target.value.toUpperCase() })}
                      className="w-8 h-8 rounded-lg bg-transparent border-0 cursor-pointer p-0 shrink-0"
                    />
                    <input
                      type="text"
                      placeholder="#10B981"
                      maxLength={7}
                      value={outletForm.accent_color}
                      onChange={(e) => setOutletForm({ ...outletForm, accent_color: e.target.value.toUpperCase() })}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-white text-xs font-mono uppercase focus:outline-none focus:border-indigo-500"
                      aria-label="Accent Color Input"
                    />
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={handleCloseOutletEdit}
                  disabled={isSavingOutlet}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSavingOutlet}
                  className="px-4 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-xs font-bold transition-colors disabled:opacity-50 flex items-center space-x-1.5"
                >
                  {isSavingOutlet ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Save Changes</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
