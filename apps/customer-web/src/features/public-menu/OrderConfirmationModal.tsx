import React from 'react';
import { Order } from '@roms/shared-types';
import { CheckCircle2, Clock, UtensilsCrossed, ShoppingBag, ArrowRight } from 'lucide-react';

interface OrderConfirmationModalProps {
  order: Order | null;
  currency: string;
  onClose: () => void;
  primaryColor?: string;
}

export const OrderConfirmationModal: React.FC<OrderConfirmationModalProps> = ({
  order,
  currency,
  onClose,
  primaryColor,
}) => {
  if (!order) return null;

  const formatPrice = (price: number | string, curr: string) => {
    const symbol = curr === 'INR' ? '₹' : curr;
    return `${symbol}${Number(price).toFixed(2)}`;
  };

  const primaryBtnStyle = primaryColor ? { backgroundColor: primaryColor } : undefined;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Order Confirmation"
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-200"
    >
      <div className="bg-white rounded-3xl max-w-sm w-full p-6 text-center relative shadow-2xl border border-gray-100 max-h-[90vh] flex flex-col overflow-hidden">
        {/* Animated Checkmark Header */}
        <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto mb-3 shadow-sm border border-emerald-200">
          <CheckCircle2 className="w-9 h-9" />
        </div>

        <h2 className="text-xl font-black text-gray-900 tracking-tight">Order Placed!</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Order Number: <strong className="font-mono text-gray-900 font-bold" data-testid="confirmed-order-number">{order.order_number}</strong>
        </p>

        {/* Status Pill & Table info */}
        <div className="flex items-center justify-center gap-2 my-3">
          <span
            data-testid="confirmed-status-badge"
            className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-50 text-amber-800 text-xs font-bold rounded-full border border-amber-200"
          >
            <Clock className="w-3.5 h-3.5 text-amber-600 animate-pulse" />
            <span>Awaiting Staff Confirmation</span>
          </span>

          {order.table_number ? (
            <span
              data-testid="confirmed-table-badge"
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 text-emerald-800 text-xs font-bold rounded-full border border-emerald-200"
            >
              <UtensilsCrossed className="w-3.5 h-3.5" />
              <span>Table {order.table_number}</span>
            </span>
          ) : (
            <span
              data-testid="confirmed-takeaway-badge"
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-50 text-blue-800 text-xs font-bold rounded-full border border-blue-200"
            >
              <ShoppingBag className="w-3.5 h-3.5" />
              <span>Takeaway</span>
            </span>
          )}
        </div>

        {/* Informational Message */}
        <div className="p-3 bg-amber-50/60 rounded-xl border border-amber-200/60 text-[11px] text-amber-900 text-left mb-3">
          <p className="font-bold mb-0.5">Kitchen notification sent</p>
          <p className="leading-relaxed text-amber-800/90">
            Your order has entered our queue. Restaurant staff will confirm it shortly and begin preparation.
          </p>
        </div>

        {/* Scrollable Order Items List */}
        <div className="flex-1 overflow-y-auto text-left border-t border-b border-gray-100 py-3 my-1 space-y-2 max-h-48">
          <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400">
            Ordered Items ({order.items.length})
          </p>
          {order.items.map((item) => (
            <div key={item.id} className="text-xs flex justify-between items-start gap-2">
              <div className="flex-1">
                <p className="font-semibold text-gray-800 leading-snug">
                  <span className="font-bold text-amber-700">{item.quantity}x</span> {item.item_name}
                </p>
                {item.special_instructions && (
                  <p className="text-[11px] text-gray-500 italic">
                    Note: {item.special_instructions}
                  </p>
                )}
              </div>
              <span className="font-mono font-bold text-gray-900 shrink-0">
                {formatPrice(item.subtotal, currency)}
              </span>
            </div>
          ))}

          {order.notes && (
            <div className="pt-2 text-[11px] text-gray-500 italic border-t border-gray-50">
              Order note: {order.notes}
            </div>
          )}
        </div>

        {/* Total & Action */}
        <div className="pt-3 flex items-center justify-between text-xs mb-4">
          <span className="font-bold text-gray-600">Total Amount</span>
          <span className="text-base font-black text-gray-900 font-mono" data-testid="confirmed-order-total">
            {formatPrice(order.total_amount, currency)}
          </span>
        </div>

        <button
          onClick={onClose}
          style={primaryBtnStyle}
          className="w-full py-3 px-4 bg-amber-600 hover:bg-amber-700 text-white font-extrabold text-xs rounded-xl shadow-md transition-all active:scale-[0.99] flex items-center justify-center gap-1.5"
          data-testid="confirmation-back-to-menu"
        >
          <span>Order More / Back to Menu</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};
