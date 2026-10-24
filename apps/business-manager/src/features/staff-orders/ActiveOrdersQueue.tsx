import React, { useState } from 'react';
import { Order, OrderStatus, PaymentMethod } from '@roms/shared-types';

interface ActiveOrdersQueueProps {
  orders: Order[];
  onUpdateStatus: (orderId: string, status: OrderStatus) => Promise<void>;
  onSettleOrder?: (orderId: string, method: PaymentMethod) => Promise<void>;
  loading: boolean;
}

export const ActiveOrdersQueue: React.FC<ActiveOrdersQueueProps> = ({
  orders,
  onUpdateStatus,
  onSettleOrder,
  loading,
}) => {
  const [settlingOrder, setSettlingOrder] = useState<Order | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash');
  const [isConfirmed, setIsConfirmed] = useState<boolean>(false);
  const [isSubmittingSettlement, setIsSubmittingSettlement] = useState<boolean>(false);
  const [settlementError, setSettlementError] = useState<string | null>(null);

  const getStatusBadge = (status: OrderStatus) => {
    switch (status) {
      case 'pending':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">Pending</span>;
      case 'confirmed':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">Confirmed</span>;
      case 'in_kitchen':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-400 border border-purple-500/30 animate-pulse">In Kitchen</span>;
      case 'served':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Served</span>;
      case 'completed':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-300">Completed</span>;
      case 'cancelled':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-400 border border-red-500/30">Cancelled</span>;
    }
  };

  const getPaymentBadge = (order: Order) => {
    const isPaid = order.payment_status === 'paid';
    if (isPaid) {
      return (
        <span
          data-testid={`payment-badge-${order.id}`}
          className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center space-x-1"
        >
          <span>Paid ({order.payment_method?.toUpperCase() || 'PAID'})</span>
        </span>
      );
    }
    return (
      <span
        data-testid={`payment-badge-${order.id}`}
        className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center space-x-1 animate-pulse"
      >
        <span>Unpaid</span>
      </span>
    );
  };

  const openSettlementModal = (order: Order) => {
    setSettlingOrder(order);
    setPaymentMethod('cash');
    setIsConfirmed(false);
    setSettlementError(null);
  };

  const closeSettlementModal = () => {
    if (isSubmittingSettlement) return;
    setSettlingOrder(null);
    setSettlementError(null);
  };

  const handleConfirmSettlement = async () => {
    if (!settlingOrder || !onSettleOrder || !isConfirmed || isSubmittingSettlement) return;

    try {
      setIsSubmittingSettlement(true);
      setSettlementError(null);
      await onSettleOrder(settlingOrder.id, paymentMethod);
      setSettlingOrder(null);
    } catch (err: any) {
      setSettlementError(err.message || 'Failed to settle order bill. Please try again.');
    } finally {
      setIsSubmittingSettlement(false);
    }
  };

  const activeOrders = orders.filter(
    (o) => o.status !== 'completed' && o.status !== 'cancelled'
  );

  return (
    <div className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6 relative">
      <div className="pb-4 border-b border-slate-800 mb-6 flex justify-between items-center">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center space-x-2">
            <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <span>Active Orders Queue ({activeOrders.length})</span>
          </h2>
          <p className="text-xs text-slate-400">
            Track live preparation, service progress, and bill settlement for tables
          </p>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400 text-sm">
          Loading orders...
        </div>
      ) : activeOrders.length === 0 ? (
        <div className="text-center py-12 text-slate-500 text-sm">
          No active orders in progress.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {activeOrders.map((order) => {
            const isPaid = order.payment_status === 'paid';
            const isServed = order.status === 'served';

            return (
              <div
                key={order.id}
                className={`bg-slate-900 border rounded-2xl p-5 shadow-xl flex flex-col justify-between transition-colors ${
                  isServed && !isPaid
                    ? 'border-amber-500/60 bg-slate-900/90 shadow-amber-950/20'
                    : 'border-slate-800'
                }`}
              >
                <div>
                  <div className="flex justify-between items-start pb-3 border-b border-slate-800">
                    <div>
                      <span className="text-sm font-extrabold text-white font-mono">
                        {order.order_number}
                      </span>
                      <div className="text-xs text-slate-400">
                        Table:{' '}
                        <span className="text-amber-400 font-bold">
                          {order.table_number || 'Takeaway'}
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end space-y-1">
                      {getStatusBadge(order.status)}
                      {getPaymentBadge(order)}
                    </div>
                  </div>

                  <div className="mt-3 text-[11px] text-slate-400 flex justify-between">
                    <span>Waiter: {order.waiter_name || 'Customer (QR)'}</span>
                    <span>{new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>

                  {/* Items list */}
                  <div className="mt-3 space-y-1.5 max-h-40 overflow-y-auto pr-1">
                    {order.items.map((item) => (
                      <div key={item.id} className="text-xs flex justify-between text-slate-300">
                        <span>
                          <span className="font-bold text-amber-400">{item.quantity}x</span>{' '}
                          {item.item_name}
                        </span>
                        <span className="font-mono">₹{Number(item.subtotal).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>

                  {order.notes && (
                    <div className="mt-3 p-2 rounded bg-slate-800/80 border border-slate-700/60 text-[11px] text-slate-300 italic">
                      Note: {order.notes}
                    </div>
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800 flex flex-col space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-400">Total Amount</span>
                    <span className="text-sm font-extrabold text-amber-400">
                      ₹{Number(order.total_amount).toFixed(2)}
                    </span>
                  </div>

                  {/* Settlement notice / info */}
                  {isPaid ? (
                    <div className="text-[11px] text-emerald-400/90 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-2.5 py-1.5 flex justify-between items-center font-medium">
                      <span>Settled via {order.payment_method?.toUpperCase()}</span>
                      {order.settled_by_name && <span className="text-[10px] text-emerald-300/70">by {order.settled_by_name}</span>}
                    </div>
                  ) : isServed ? (
                    <div className="text-[11px] text-amber-400/90 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2 text-center font-semibold">
                      Order served • Settle bill to release table
                    </div>
                  ) : null}

                  {/* Action buttons */}
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    {order.status === 'pending' && (
                      <button
                        onClick={() => onUpdateStatus(order.id, 'confirmed')}
                        className="col-span-2 py-1.5 rounded-lg bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 border border-blue-500/30 text-xs font-bold transition-colors"
                      >
                        Confirm Order
                      </button>
                    )}
                    {order.status === 'confirmed' && (
                      <button
                        onClick={() => onUpdateStatus(order.id, 'in_kitchen')}
                        className="col-span-2 py-1.5 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-400 border border-purple-500/30 text-xs font-bold transition-colors"
                      >
                        Send to Kitchen
                      </button>
                    )}
                    {order.status === 'in_kitchen' && (
                      <button
                        onClick={() => onUpdateStatus(order.id, 'served')}
                        className="col-span-2 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 text-xs font-bold transition-colors"
                      >
                        Mark as Served
                      </button>
                    )}

                    {/* Settle Bill button for unpaid orders */}
                    {!isPaid && onSettleOrder && (
                      <button
                        onClick={() => openSettlementModal(order)}
                        data-testid={`settle-btn-${order.id}`}
                        className={`col-span-2 py-2 rounded-lg text-xs font-extrabold transition-all shadow-md ${
                          isServed
                            ? 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-amber-500/20'
                            : 'bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30'
                        }`}
                      >
                        Settle Bill (Cash / UPI)
                      </button>
                    )}

                    {/* Complete & Free Table: Only enabled when paid */}
                    {isServed && isPaid && (
                      <button
                        onClick={() => onUpdateStatus(order.id, 'completed')}
                        data-testid={`complete-btn-${order.id}`}
                        className="col-span-2 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-slate-950 text-xs font-extrabold transition-colors shadow-lg shadow-emerald-500/20"
                      >
                        Complete & Free Table
                      </button>
                    )}

                    <button
                      onClick={() => onUpdateStatus(order.id, 'cancelled')}
                      className="col-span-2 py-1 rounded-lg text-[10px] text-red-400/70 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    >
                      Cancel Order
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Bill Settlement Modal */}
      {settlingOrder && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Settle Order Bill"
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150"
        >
          <div className="bg-slate-900 border border-slate-700/80 rounded-3xl max-w-sm w-full p-6 text-slate-100 shadow-2xl space-y-4">
            <div className="flex justify-between items-start border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-black text-white tracking-tight">Settle Order Bill</h3>
                <p className="text-xs text-slate-400 font-mono mt-0.5">
                  #{settlingOrder.order_number} • Table {settlingOrder.table_number || 'Takeaway'}
                </p>
              </div>
              <button
                onClick={closeSettlementModal}
                disabled={isSubmittingSettlement}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Total due display */}
            <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 flex justify-between items-center">
              <span className="text-xs text-slate-400 font-bold uppercase tracking-wider">Amount Due</span>
              <span className="text-xl font-black text-amber-400 font-mono" data-testid="settle-modal-amount">
                ₹{Number(settlingOrder.total_amount).toFixed(2)}
              </span>
            </div>

            {/* Payment Method Selector */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-300">Select Payment Method</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setPaymentMethod('cash')}
                  data-testid="method-cash-btn"
                  className={`py-2.5 px-3 rounded-xl border text-xs font-extrabold flex items-center justify-center space-x-2 transition-all ${
                    paymentMethod === 'cash'
                      ? 'bg-amber-500 text-slate-950 border-amber-400 shadow-md shadow-amber-500/20'
                      : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-800'
                  }`}
                >
                  <span>💵 Cash</span>
                </button>
                <button
                  type="button"
                  onClick={() => setPaymentMethod('upi')}
                  data-testid="method-upi-btn"
                  className={`py-2.5 px-3 rounded-xl border text-xs font-extrabold flex items-center justify-center space-x-2 transition-all ${
                    paymentMethod === 'upi'
                      ? 'bg-amber-500 text-slate-950 border-amber-400 shadow-md shadow-amber-500/20'
                      : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-800'
                  }`}
                >
                  <span>📱 UPI QR</span>
                </button>
              </div>
            </div>

            {/* Explicit confirmation checkbox */}
            <label className="flex items-start space-x-2.5 pt-1 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={isConfirmed}
                onChange={(e) => setIsConfirmed(e.target.checked)}
                data-testid="settle-confirm-checkbox"
                className="mt-0.5 w-4 h-4 rounded border-slate-700 bg-slate-950 text-amber-500 focus:ring-amber-500/50 cursor-pointer"
              />
              <span className="text-xs text-slate-300 leading-tight">
                I explicitly confirm payment of{' '}
                <strong className="text-white">₹{Number(settlingOrder.total_amount).toFixed(2)}</strong> was
                collected via <strong className="text-amber-400 uppercase">{paymentMethod}</strong>.
              </span>
            </label>

            {/* Error display */}
            {settlementError && (
              <div
                data-testid="settle-error-banner"
                className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-xs text-red-400 leading-tight"
              >
                {settlementError}
              </div>
            )}

            {/* Modal actions */}
            <div className="pt-2 flex items-center space-x-2">
              <button
                type="button"
                onClick={closeSettlementModal}
                disabled={isSubmittingSettlement}
                className="flex-1 py-2.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmSettlement}
                disabled={!isConfirmed || isSubmittingSettlement}
                data-testid="settle-confirm-submit-btn"
                className={`flex-1 py-2.5 px-3 rounded-xl text-xs font-black transition-all ${
                  isConfirmed && !isSubmittingSettlement
                    ? 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-lg shadow-emerald-500/20'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50'
                }`}
              >
                {isSubmittingSettlement ? 'Settling...' : 'Confirm Settlement'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
