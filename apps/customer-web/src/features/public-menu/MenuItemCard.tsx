import React from 'react';
import { MenuItem } from '@roms/shared-types';
import { Utensils, AlertCircle, Plus, Minus } from 'lucide-react';

interface MenuItemCardProps {
  item: MenuItem;
  currency: string;
  quantity?: number;
  onAddToCart?: (item: MenuItem) => void;
  onIncrement?: (itemId: string) => void;
  onDecrement?: (itemId: string) => void;
  primaryColor?: string;
}

export const MenuItemCard: React.FC<MenuItemCardProps> = ({
  item,
  currency,
  quantity = 0,
  onAddToCart,
  onIncrement,
  onDecrement,
  primaryColor,
}) => {
  const formatPrice = (price: number, curr: string) => {
    const symbol = curr === 'INR' ? '₹' : curr;
    return `${symbol}${Number(price).toFixed(2)}`;
  };

  const buttonStyle = primaryColor ? { backgroundColor: primaryColor } : undefined;

  return (
    <div
      className={`relative flex gap-4 p-4 rounded-xl border transition-all ${
        item.is_available
          ? 'bg-white border-gray-100 shadow-sm hover:shadow-md'
          : 'bg-gray-50/80 border-gray-200 opacity-75'
      }`}
    >
      {/* Left Text Info */}
      <div className="flex-1 flex flex-col justify-between">
        <div>
          <div className="flex items-start justify-between gap-2 mb-1">
            <h3 className={`font-semibold text-gray-900 leading-snug ${!item.is_available && 'line-through text-gray-500'}`}>
              {item.name}
            </h3>
          </div>
          {item.description && (
            <p className="text-xs text-gray-600 leading-relaxed line-clamp-2 mb-3">
              {item.description}
            </p>
          )}
        </div>

        <div className="flex items-center justify-between mt-auto pt-2">
          <span className="font-bold text-amber-700 text-base">
            {formatPrice(item.price, currency)}
          </span>

          {!item.is_available ? (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
              <AlertCircle className="w-3 h-3" />
              Sold Out
            </span>
          ) : (
            <div>
              {quantity === 0 ? (
                onAddToCart && (
                  <button
                    onClick={() => onAddToCart(item)}
                    style={buttonStyle}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold rounded-lg shadow-xs transition-all active:scale-95"
                    aria-label={`Add ${item.name} to cart`}
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add</span>
                  </button>
                )
              ) : (
                <div className="inline-flex items-center bg-amber-50 border border-amber-200 rounded-lg p-0.5 shadow-xs">
                  <button
                    onClick={() => onDecrement?.(item.id)}
                    className="w-7 h-7 flex items-center justify-center rounded-md bg-white text-amber-900 hover:bg-amber-100 shadow-2xs font-bold text-xs transition-all active:scale-90"
                    aria-label={`Decrease ${item.name} quantity`}
                  >
                    <Minus className="w-3.5 h-3.5" />
                  </button>
                  <span
                    className="w-7 text-center font-extrabold text-xs text-amber-950 font-mono"
                    aria-label={`${item.name} quantity`}
                  >
                    {quantity}
                  </span>
                  <button
                    onClick={() => onIncrement?.(item.id)}
                    disabled={quantity >= 99}
                    style={buttonStyle}
                    className="w-7 h-7 flex items-center justify-center rounded-md bg-amber-600 text-white hover:bg-amber-700 shadow-2xs font-bold text-xs transition-all active:scale-90 disabled:opacity-50"
                    aria-label={`Increase ${item.name} quantity`}
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right Image or Placeholder */}
      <div className="w-24 h-24 rounded-lg bg-gray-100 flex-shrink-0 overflow-hidden relative border border-gray-100">
        {item.image_url ? (
          <img
            src={item.image_url}
            alt={item.name}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 bg-amber-50/40">
            <Utensils className="w-6 h-6 text-amber-300 mb-1" />
            <span className="text-[10px] text-gray-400">ROMS</span>
          </div>
        )}
      </div>
    </div>
  );
};
