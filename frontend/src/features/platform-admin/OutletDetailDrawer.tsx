import React, { useState, useEffect } from 'react';
import { PlatformBusiness, PlatformOutlet } from '../../types/platform';
import { EffectiveEntitlementsTab } from './EffectiveEntitlementsTab';

export interface OutletDetailDrawerProps {
  business: PlatformBusiness | null;
  isOpen: boolean;
  onClose: () => void;
  onAddOutlet?: (biz: PlatformBusiness) => void;
  onEditSubscription?: (biz: PlatformBusiness) => void;
  onAssignOwner?: (bizId: string, outlet: PlatformOutlet) => void;
}

export const OutletDetailDrawer: React.FC<OutletDetailDrawerProps> = ({
  business,
  isOpen,
  onClose,
  onAddOutlet,
  onEditSubscription,
  onAssignOwner,
}) => {
  const [activeTab, setActiveTab] = useState<'outlets' | 'entitlements'>('outlets');

  // Close drawer on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !business) return null;

  const currentOutletCount = business.outlets?.length || 0;
  const maxOutlets = business.max_outlets;
  const isLimitReached = maxOutlets !== null && maxOutlets !== undefined && currentOutletCount >= maxOutlets;

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
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1.5">
                <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                  Tenant Detail Drawer
                </span>
                {renderAccountBadge(business.status)}
                {renderSubscriptionBadge(business.subscription_status)}
              </div>
              <h2 className="text-xl font-black text-white tracking-tight">{business.name}</h2>
              <p className="text-xs text-slate-400 mt-1">
                Registered ID: <span className="font-mono text-slate-300">{business.id}</span>
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
          </div>
        </div>

        {/* Drawer Content */}
        <div className="p-6 space-y-6 flex-1">
          {activeTab === 'entitlements' ? (
            <EffectiveEntitlementsTab business={business} />
          ) : (
            <>

          {/* Tenant Business Summary Grid */}
          <div className="bg-slate-950/60 border border-slate-800 rounded-2xl p-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-semibold">Plan Tier</span>
              <span className="font-bold text-white capitalize mt-0.5 block">
                {business.plan_name || 'Unassigned'}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-semibold">Outlet Capacity</span>
              <span className="font-bold text-white mt-0.5 block">
                {currentOutletCount} / {maxOutlets !== null && maxOutlets !== undefined ? maxOutlets : '∞'}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-semibold">Created Date</span>
              <span className="font-bold text-slate-300 font-mono text-[11px] mt-0.5 block">
                {business.created_at ? new Date(business.created_at).toLocaleDateString() : 'N/A'}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-semibold">Trial Status</span>
              <span className="font-bold text-slate-300 text-[11px] mt-0.5 block">
                {business.trial_ends_at ? `Expires ${new Date(business.trial_ends_at).toLocaleDateString()}` : 'N/A'}
              </span>
            </div>
          </div>

          {/* Quick Actions Bar */}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            {onEditSubscription && (
              <button
                onClick={() => onEditSubscription(business)}
                className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition-colors flex items-center space-x-1.5"
              >
                <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
                <span>Edit Subscription & Status</span>
              </button>
            )}

            {onAddOutlet && (
              <button
                disabled={isLimitReached}
                onClick={() => onAddOutlet(business)}
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
                Physical and digital menu branches registered under {business.name}
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
              {onAddOutlet && (
                <button
                  onClick={() => onAddOutlet(business)}
                  className="mt-2 px-3.5 py-1.5 rounded-xl bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-500/40 text-indigo-300 text-xs font-bold transition-colors"
                >
                  Add Primary Outlet
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {business.outlets.map((outlet) => (
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

                    {onAssignOwner && (
                      <button
                        onClick={() => onAssignOwner(business.id, outlet)}
                        className="px-3 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-semibold transition-colors"
                      >
                        Assign Owner
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          </>
          )}
        </div>
      </div>
    </div>
  );
};
