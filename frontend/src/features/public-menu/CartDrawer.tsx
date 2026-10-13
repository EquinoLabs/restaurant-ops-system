import React, { useState } from 'react';
import { CartItem } from '../../types/orders';
import {
  X,
  Trash2,
  Plus,
  Minus,
  MessageSquare,
  AlertCircle,
  Loader2,
  UtensilsCrossed,
  ShoppingBag,
} from 'lucide-react';

interface CartDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  items: CartItem[];
  currency: string;
  tableNumber: string | null;
  onIncrement: (itemId: string) => void;
  onDecrement: (itemId: string) => void;
  onRemoveItem: (itemId: string) => void;
  onUpdateInstructions: (itemId: string, instructions: string) => void;
  orderNotes: string;
  onChangeOrderNotes: (notes: string) => void;
  onClearCart: () => void;
  onSubmitOrder: () => void;
  isSubmitting: boolean;
  submitError: string | null;
  onClearError: () => void;
  primaryColor?: string;
}

export const CartDrawer: React.FC<CartDrawerProps> = ({
  isOpen,
  onClose,
  items,
  currency,
  tableNumber,
  onIncrement,
  onDecrement,
  onRemoveItem,
  onUpdateInstructions,
  orderNotes,
  onChangeOrderNotes,
  onClearCart,
  onSubmitOrder,
  isSubmitting,
  submitError,
  onClearError,
  primaryColor,
}) => {
  const [editingInstructionsId, setEditingInstructionsId] = useState<string | null>(null);

  if (!isOpen) return null;

  const formatPrice = (price: number, curr: string) => {
    const symbol = curr === 'INR' ? '₹' : curr;
    return `${symbol}${Number(price).toFixed(2)}`;
  };

  const totalAmount = items.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const totalItemsCount = items.reduce((sum, item) => sum + item.quantity, 0);

  const primaryBtnStyle = primaryColor ? { backgroundColor: primaryColor } : undefined;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Your Order Cart"
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4 animate-in fade-in duration-200"
    >
      {/* Drawer Container */}
      <div className="bg-white w-full max-w-md rounded-t-3xl sm:rounded-3xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden border border-gray-100">
        {/* Header */}
        <header className="p-4 sm:p-5 border-b border-gray-100 flex items-center justify-between bg-white sticky top-0 z-10">
          <div className="flex items-center gap-2.5">
            <h2 className="text-lg font-extrabold text-gray-900 tracking-tight">Your Order</h2>
            {tableNumber ? (
              <span
                data-testid="cart-table-badge"
                className="inline-flex items-center gap-1 text-xs font-bold text-emerald-800 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200"
              >
                <UtensilsCrossed className="w-3.5 h-3.5" />
                Table {tableNumber}
              </span>
            ) : (
              <span
                data-testid="cart-takeaway-badge"
                className="inline-flex items-center gap-1 text-xs font-bold text-blue-800 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-200"
              >
                <ShoppingBag className="w-3.5 h-3.5" />
                Takeaway
              </span>
            )}
          </div>

          <button
            onClick={onClose}
            aria-label="Close cart drawer"
            className="text-gray-400 hover:text-gray-700 p-1.5 rounded-full hover:bg-gray-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </header>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
          {submitError && (
            <div
              role="alert"
              className="p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-start justify-between gap-2 shadow-2xs"
            >
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold">Order could not be placed</p>
                  <p className="mt-0.5 leading-relaxed">{submitError}</p>
                  <p className="text-[11px] text-red-600/80 mt-1">
                    Your cart items have been saved. You can try again now.
                  </p>
                </div>
              </div>
              <button
                onClick={onClearError}
                aria-label="Dismiss error"
                className="text-red-400 hover:text-red-700 p-1"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {items.length === 0 ? (
            <div className="text-center py-12 px-4 space-y-3">
              <div className="w-14 h-14 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center mx-auto border border-amber-200">
                <ShoppingBag className="w-7 h-7" />
              </div>
              <p className="text-sm font-bold text-gray-800">Your cart is empty</p>
              <p className="text-xs text-gray-500 max-w-xs mx-auto">
                Explore the menu and add items to place your order directly from your table.
              </p>
              <button
                onClick={onClose}
                className="mt-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-bold rounded-xl transition-colors"
              >
                Back to Menu
              </button>
            </div>
          ) : (
            <div className="space-y-3 divide-y divide-gray-100">
              {items.map((item) => (
                <div key={item.menu_item_id} className="pt-3 first:pt-0 space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <h3 className="text-sm font-bold text-gray-900 leading-snug">{item.name}</h3>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {formatPrice(item.price, currency)} each
                      </p>
                    </div>

                    {/* Stepper + Remove */}
                    <div className="flex items-center gap-2">
                      <div className="inline-flex items-center bg-gray-50 border border-gray-200 rounded-lg p-0.5">
                        <button
                          onClick={() => onDecrement(item.menu_item_id)}
                          aria-label={`Decrease ${item.name} quantity`}
                          className="w-6 h-6 flex items-center justify-center rounded-md bg-white text-gray-700 hover:bg-gray-100 shadow-2xs font-bold text-xs"
                        >
                          <Minus className="w-3 h-3" />
                        </button>
                        <span className="w-6 text-center font-bold text-xs text-gray-900 font-mono">
                          {item.quantity}
                        </span>
                        <button
                          onClick={() => onIncrement(item.menu_item_id)}
                          disabled={item.quantity >= 99}
                          aria-label={`Increase ${item.name} quantity`}
                          className="w-6 h-6 flex items-center justify-center rounded-md bg-amber-600 text-white hover:bg-amber-700 shadow-2xs font-bold text-xs disabled:opacity-50"
                        >
                          <Plus className="w-3 h-3" />
                        </button>
                      </div>

                      <button
                        onClick={() => onRemoveItem(item.menu_item_id)}
                        aria-label={`Remove ${item.name} from cart`}
                        className="text-gray-400 hover:text-red-500 p-1.5 rounded-lg hover:bg-red-50 transition-colors"
                        title="Remove item"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Subtotal */}
                  <div className="flex items-center justify-between text-xs pt-1">
                    <button
                      onClick={() =>
                        setEditingInstructionsId(
                          editingInstructionsId === item.menu_item_id ? null : item.menu_item_id
                        )
                      }
                      className="inline-flex items-center gap-1 text-[11px] text-amber-700 hover:text-amber-800 font-medium"
                    >
                      <MessageSquare className="w-3 h-3" />
                      <span>
                        {item.special_instructions
                          ? 'Edit note'
                          : '+ Add special note'}
                      </span>
                    </button>
                    <span className="font-extrabold text-gray-900 font-mono">
                      {formatPrice(item.price * item.quantity, currency)}
                    </span>
                  </div>

                  {/* Special Instructions Field */}
                  {(editingInstructionsId === item.menu_item_id || item.special_instructions) && (
                    <div className="mt-1">
                      <input
                        type="text"
                        placeholder="e.g. Less spicy, no onion, extra ice (optional)"
                        maxLength={500}
                        value={item.special_instructions || ''}
                        onChange={(e) => onUpdateInstructions(item.menu_item_id, e.target.value)}
                        className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-gray-200 bg-gray-50/70 focus:bg-white focus:border-amber-400 focus:outline-none transition-all placeholder-gray-400"
                        aria-label={`Special instructions for ${item.name}`}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* General Order Notes */}
          {items.length > 0 && (
            <div className="pt-3 border-t border-gray-100">
              <label
                htmlFor="cart-order-notes"
                className="block text-xs font-bold text-gray-700 mb-1.5"
              >
                Special Requests for Outlet (Optional)
              </label>
              <textarea
                id="cart-order-notes"
                rows={2}
                maxLength={500}
                placeholder="e.g. Need high chair, bring cutlery, allergen warnings..."
                value={orderNotes}
                onChange={(e) => onChangeOrderNotes(e.target.value)}
                className="w-full text-xs p-2.5 rounded-xl border border-gray-200 bg-gray-50/70 focus:bg-white focus:border-amber-400 focus:outline-none transition-all placeholder-gray-400 resize-none"
              />
            </div>
          )}

          {/* Price Breakdown / Disclaimer */}
          {items.length > 0 && (
            <div className="p-3 rounded-xl bg-gray-50 border border-gray-100 text-xs space-y-1.5 text-gray-600">
              <div className="flex justify-between">
                <span>Items Subtotal ({totalItemsCount})</span>
                <span className="font-mono font-bold text-gray-900">
                  {formatPrice(totalAmount, currency)}
                </span>
              </div>
              <p className="text-[11px] text-gray-400 pt-1 border-t border-gray-200/50">
                Prices include applicable taxes. Order will be verified and prepared upon staff confirmation.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        {items.length > 0 && (
          <footer className="p-4 sm:p-5 border-t border-gray-100 bg-white sticky bottom-0 space-y-2.5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-gray-500 font-medium">Total Amount</p>
                <p className="text-lg font-black text-gray-900 tracking-tight" data-testid="cart-modal-total">
                  {formatPrice(totalAmount, currency)}
                </p>
              </div>

              <button
                onClick={onClearCart}
                disabled={isSubmitting}
                className="text-xs text-gray-400 hover:text-red-500 font-semibold transition-colors disabled:opacity-50"
              >
                Clear Cart
              </button>
            </div>

            <button
              onClick={onSubmitOrder}
              disabled={isSubmitting || items.length === 0}
              style={primaryBtnStyle}
              className="w-full py-3.5 px-4 bg-amber-600 hover:bg-amber-700 text-white font-extrabold text-sm rounded-2xl shadow-lg transition-all active:scale-[0.99] disabled:opacity-50 flex items-center justify-center gap-2"
              data-testid="place-order-button"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Placing Order...</span>
                </>
              ) : (
                <span>
                  Confirm & Place Order ({formatPrice(totalAmount, currency)})
                </span>
              )}
            </button>
          </footer>
        )}
      </div>
    </div>
  );
};
