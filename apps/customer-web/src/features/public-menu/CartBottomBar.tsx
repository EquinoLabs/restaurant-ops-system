import React from 'react';
import { ShoppingBag, ChevronRight } from 'lucide-react';

interface CartBottomBarProps {
  totalItems: number;
  totalAmount: number;
  currency: string;
  onOpenCart: () => void;
  primaryColor?: string;
}

export const CartBottomBar: React.FC<CartBottomBarProps> = ({
  totalItems,
  totalAmount,
  currency,
  onOpenCart,
  primaryColor,
}) => {
  if (totalItems <= 0) return null;

  const formatPrice = (price: number, curr: string) => {
    const symbol = curr === 'INR' ? '₹' : curr;
    return `${symbol}${Number(price).toFixed(2)}`;
  };

  const barStyle = primaryColor ? { backgroundColor: primaryColor } : undefined;

  return (
    <aside
      aria-label="Cart summary"
      className="fixed bottom-4 left-4 right-4 max-w-md mx-auto z-30 animate-in fade-in slide-in-from-bottom-4 duration-200"
    >
      <button
        onClick={onOpenCart}
        style={barStyle}
        className="w-full bg-amber-600 hover:bg-amber-700 text-white p-3.5 rounded-2xl shadow-xl flex items-center justify-between transition-all active:scale-[0.99] border border-white/20"
        aria-label={`View cart: ${totalItems} items, total ${formatPrice(totalAmount, currency)}`}
      >
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-white/20 backdrop-blur-xs">
            <ShoppingBag className="w-5 h-5 text-white" />
            <span
              className="absolute -top-1.5 -right-1.5 bg-white text-amber-900 text-[11px] font-black w-5 h-5 rounded-full flex items-center justify-center shadow-xs"
              data-testid="cart-badge-count"
            >
              {totalItems}
            </span>
          </div>
          <div className="text-left">
            <p className="text-xs font-semibold text-white/90">
              {totalItems} item{totalItems > 1 ? 's' : ''} added
            </p>
            <p className="text-sm font-extrabold text-white tracking-tight" data-testid="cart-bar-total">
              {formatPrice(totalAmount, currency)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 text-xs font-bold bg-white/20 hover:bg-white/30 px-3.5 py-2 rounded-xl backdrop-blur-xs transition-colors">
          <span>View Cart</span>
          <ChevronRight className="w-4 h-4" />
        </div>
      </button>
    </aside>
  );
};
