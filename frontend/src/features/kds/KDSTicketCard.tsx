import React from 'react';
import { Order, OrderStatus } from '../../types/orders';

interface KDSTicketCardProps {
  order: Order;
  onUpdateStatus: (orderId: string, status: OrderStatus) => Promise<void>;
  isSubmitting: boolean;
  now: number;
}

export const KDSTicketCard: React.FC<KDSTicketCardProps> = ({
  order,
  onUpdateStatus,
  isSubmitting,
  now,
}) => {
  // Compute elapsed preparation time from order.created_at
  const createdAtTime = new Date(order.created_at).getTime();
  const elapsedMs = Math.max(0, now - (isNaN(createdAtTime) ? now : createdAtTime));
  const elapsedMinutes = Math.floor(elapsedMs / 60000);
  const elapsedSeconds = Math.floor((elapsedMs % 60000) / 1000);

  // Timer urgency color coding
  let timerBadgeStyle = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
  let urgencyLabel = 'Normal';

  if (elapsedMinutes >= 20) {
    timerBadgeStyle = 'bg-red-500/20 text-red-400 border-red-500/40 animate-pulse font-bold';
    urgencyLabel = 'Delayed';
  } else if (elapsedMinutes >= 10) {
    timerBadgeStyle = 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    urgencyLabel = 'Priority';
  }

  // Determine next permitted order action
  let nextAction: { label: string; targetStatus: OrderStatus; style: string } | null = null;

  if (order.status === 'pending' || order.status === 'confirmed') {
    nextAction = {
      label: 'Start Cooking',
      targetStatus: 'in_kitchen',
      style: 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-amber-500/20',
    };
  } else if (order.status === 'in_kitchen') {
    nextAction = {
      label: 'Mark Ready (Bump)',
      targetStatus: 'served',
      style: 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-emerald-500/20',
    };
  } else if (order.status === 'served') {
    nextAction = {
      label: 'Complete Order',
      targetStatus: 'completed',
      style: 'bg-slate-700 hover:bg-slate-600 text-slate-200 border border-slate-600',
    };
  }

  const handleActionClick = async () => {
    if (!nextAction || isSubmitting) return;
    await onUpdateStatus(order.id, nextAction.targetStatus);
  };

  return (
    <div
      className={`flex flex-col justify-between rounded-2xl border bg-slate-900/90 shadow-xl transition-all duration-200 overflow-hidden ${
        elapsedMinutes >= 20
          ? 'border-red-500/50 shadow-red-950/40'
          : order.status === 'in_kitchen'
          ? 'border-amber-500/40 shadow-slate-950'
          : order.status === 'served'
          ? 'border-emerald-500/40 opacity-90'
          : 'border-slate-800'
      }`}
    >
      {/* Ticket Header */}
      <div className="p-4 bg-slate-800/80 border-b border-slate-800 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-lg font-black text-white tracking-tight">
              #{order.order_number}
            </span>
            <span
              className={`px-2 py-0.5 text-[10px] font-extrabold tracking-wider uppercase rounded-md border ${
                order.order_type?.toLowerCase() === 'takeaway'
                  ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
                  : 'bg-blue-500/20 text-blue-300 border-blue-500/30'
              }`}
            >
              {order.order_type || 'Dine-In'}
            </span>
          </div>

          <div className="mt-1 flex items-center space-x-3 text-xs text-slate-300">
            {order.table_number ? (
              <span className="font-bold text-amber-400">Table {order.table_number}</span>
            ) : (
              <span className="text-slate-400 italic">No Table</span>
            )}
            {order.waiter_name && (
              <span className="text-slate-400">
                • Waiter: <strong className="text-slate-200">{order.waiter_name}</strong>
              </span>
            )}
          </div>
        </div>

        {/* Dynamic Timer Badge */}
        <div className="text-right flex flex-col items-end">
          <div
            className={`px-2.5 py-1 rounded-xl text-xs font-mono font-bold border flex items-center space-x-1.5 ${timerBadgeStyle}`}
            title={`Created at ${new Date(order.created_at).toLocaleTimeString()}`}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>
              {elapsedMinutes}m {elapsedSeconds.toString().padStart(2, '0')}s
            </span>
          </div>
          <span className="mt-1 text-[10px] font-bold text-slate-400 uppercase tracking-wide">
            {urgencyLabel}
          </span>
        </div>
      </div>

      {/* Ticket Body: Items & Instructions */}
      <div className="p-4 flex-1 space-y-3 divide-y divide-slate-800/60">
        <div className="space-y-2.5">
          {order.items.map((item) => (
            <div key={item.id} className="text-sm">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-start space-x-2.5">
                  <span className="px-2 py-0.5 rounded-lg bg-amber-500/20 text-amber-400 font-black text-sm border border-amber-500/30">
                    {item.quantity}x
                  </span>
                  <span className="font-bold text-slate-100 leading-snug">
                    {item.item_name}
                  </span>
                </div>
              </div>

              {/* Special Instructions (Amber Highlighting) */}
              {item.special_instructions && (
                <div className="mt-1.5 ml-8 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs italic flex items-start space-x-1.5">
                  <svg className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>"{item.special_instructions}"</span>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Order-Level Notes */}
        {order.notes && (
          <div className="pt-2 text-xs text-slate-300">
            <span className="font-bold text-slate-400 uppercase tracking-wide text-[10px]">Order Notes:</span>
            <p className="mt-0.5 p-2 rounded-lg bg-slate-800/80 border border-slate-700/60 text-slate-200">
              {order.notes}
            </p>
          </div>
        )}
      </div>

      {/* Ticket Footer: Status Action Button */}
      <div className="p-4 bg-slate-950/60 border-t border-slate-800">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-semibold text-slate-400 capitalize">
            Status: <strong className="text-slate-200">{order.status.replace('_', ' ')}</strong>
          </span>

          {nextAction ? (
            <button
              onClick={handleActionClick}
              disabled={isSubmitting}
              className={`px-4 py-2.5 rounded-xl font-extrabold text-xs tracking-tight transition-all shadow-lg flex items-center space-x-2 ${
                nextAction.style
              } ${isSubmitting ? 'opacity-50 cursor-not-allowed' : 'active:scale-95'}`}
            >
              {isSubmitting ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
                  <span>Updating...</span>
                </>
              ) : (
                <span>{nextAction.label}</span>
              )}
            </button>
          ) : (
            <span className="text-xs text-slate-500 italic">No further actions</span>
          )}
        </div>
      </div>
    </div>
  );
};
