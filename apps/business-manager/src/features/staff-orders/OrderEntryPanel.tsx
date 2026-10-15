import React, { useState } from 'react';
import { DiningTable, OrderPayload } from '@roms/shared-types';
import { AdminMenuCategory, AdminMenuItem } from '@roms/shared-types';

interface OrderTicketItem {
  item: AdminMenuItem;
  quantity: number;
  special_instructions: string;
}

interface OrderEntryPanelProps {
  selectedTable: DiningTable | null;
  categories: AdminMenuCategory[];
  onOrderSubmitted: (payload: OrderPayload) => Promise<void>;
  currency?: string;
}

export const OrderEntryPanel: React.FC<OrderEntryPanelProps> = ({
  selectedTable,
  categories,
  onOrderSubmitted,
}) => {
  const [ticketItems, setTicketItems] = useState<OrderTicketItem[]>([]);
  const [activeCategoryId, setActiveCategoryId] = useState<string>(
    categories[0]?.id || ''
  );
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAddItem = (item: AdminMenuItem) => {
    if (!item.is_available || !item.is_active) return;
    setTicketItems((prev) => {
      const existing = prev.find((t) => t.item.id === item.id);
      if (existing) {
        return prev.map((t) =>
          t.item.id === item.id ? { ...t, quantity: t.quantity + 1 } : t
        );
      }
      return [...prev, { item, quantity: 1, special_instructions: '' }];
    });
  };

  const handleUpdateQuantity = (itemId: string, delta: number) => {
    setTicketItems((prev) =>
      prev
        .map((t) => {
          if (t.item.id === itemId) {
            const newQty = t.quantity + delta;
            return newQty > 0 ? { ...t, quantity: newQty } : null;
          }
          return t;
        })
        .filter(Boolean) as OrderTicketItem[]
    );
  };

  const handleUpdateInstructions = (itemId: string, instructions: string) => {
    setTicketItems((prev) =>
      prev.map((t) =>
        t.item.id === itemId ? { ...t, special_instructions: instructions } : t
      )
    );
  };

  const calculateTotal = () => {
    return ticketItems.reduce(
      (sum, t) => sum + Number(t.item.price) * t.quantity,
      0
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (ticketItems.length === 0) {
      setError('Please add at least one menu item to the order ticket.');
      return;
    }

    try {
      setIsSubmitting(true);
      await onOrderSubmitted({
        table_id: selectedTable?.id || null,
        order_type: 'dine_in',
        items: ticketItems.map((t) => ({
          menu_item_id: t.item.id,
          quantity: t.quantity,
          special_instructions: t.special_instructions.trim() || null,
        })),
        notes: notes.trim() || null,
      });

      // Reset ticket
      setTicketItems([]);
      setNotes('');
    } catch (err: any) {
      setError(err.message || 'Failed to submit order.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeCategory =
    categories.find((c) => c.id === activeCategoryId) || categories[0];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Menu Item Picker */}
      <div className="lg:col-span-2 bg-slate-900/60 rounded-2xl border border-slate-800 p-6 flex flex-col justify-between">
        <div>
          <div className="pb-4 border-b border-slate-800 mb-4">
            <h3 className="text-lg font-bold text-white">Select Menu Items</h3>
            <p className="text-xs text-slate-400">
              Tap any item to add it to the order ticket
            </p>
          </div>

          {/* Category Tabs */}
          <div className="flex space-x-2 overflow-x-auto pb-3 scrollbar-thin">
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setActiveCategoryId(cat.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors ${
                  activeCategoryId === cat.id
                    ? 'bg-amber-500 text-slate-950 font-bold'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
              >
                {cat.name}
              </button>
            ))}
          </div>

          {/* Items Grid */}
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
            {activeCategory?.items.map((item) => (
              <button
                key={item.id}
                disabled={!item.is_available || !item.is_active}
                onClick={() => handleAddItem(item)}
                className={`p-3.5 rounded-xl border text-left transition-all flex flex-col justify-between h-24 ${
                  !item.is_available || !item.is_active
                    ? 'bg-slate-900/30 border-slate-800 opacity-50 cursor-not-allowed'
                    : 'bg-slate-800/80 border-slate-700 hover:border-amber-500/50 hover:bg-slate-800 cursor-pointer'
                }`}
              >
                <div>
                  <div className="flex justify-between items-start">
                    <span className="text-xs font-bold text-white line-clamp-1">
                      {item.name}
                    </span>
                    {!item.is_available && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30">
                        Out of Stock
                      </span>
                    )}
                  </div>
                  {item.description && (
                    <p className="text-[11px] text-slate-400 line-clamp-1 mt-0.5">
                      {item.description}
                    </p>
                  )}
                </div>
                <div className="text-xs font-extrabold text-amber-400 mt-2">
                  ₹{Number(item.price).toFixed(2)}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Order Ticket Panel */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between shadow-2xl">
        <div>
          <div className="pb-4 border-b border-slate-800 mb-4 flex justify-between items-center">
            <div>
              <h3 className="text-base font-bold text-white">Order Ticket</h3>
              <p className="text-xs text-slate-400">
                Table:{' '}
                <span className="text-amber-400 font-bold">
                  {selectedTable ? selectedTable.table_number : 'Walk-in / Takeaway'}
                </span>
              </p>
            </div>
            {ticketItems.length > 0 && (
              <button
                onClick={() => setTicketItems([])}
                className="text-xs text-red-400 hover:text-red-300 transition-colors"
              >
                Clear Ticket
              </button>
            )}
          </div>

          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
              {error}
            </div>
          )}

          {/* Ticket Items List */}
          <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
            {ticketItems.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-xs">
                No items added yet. Tap items from the left to build order.
              </div>
            ) : (
              ticketItems.map((t) => (
                <div
                  key={t.item.id}
                  className="p-3 rounded-xl bg-slate-800/80 border border-slate-700/80"
                >
                  <div className="flex justify-between items-start text-xs">
                    <span className="font-bold text-white">{t.item.name}</span>
                    <span className="font-extrabold text-amber-400">
                      ₹{(Number(t.item.price) * t.quantity).toFixed(2)}
                    </span>
                  </div>

                  <div className="mt-2 flex justify-between items-center">
                    <input
                      type="text"
                      value={t.special_instructions}
                      onChange={(e) =>
                        handleUpdateInstructions(t.item.id, e.target.value)
                      }
                      placeholder="Special note (e.g. Less spicy)..."
                      className="text-[11px] px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-300 placeholder-slate-500 w-36 focus:outline-none"
                    />

                    <div className="flex items-center space-x-1.5 bg-slate-900 px-2 py-1 rounded-lg border border-slate-700">
                      <button
                        onClick={() => handleUpdateQuantity(t.item.id, -1)}
                        className="text-slate-400 hover:text-white font-bold text-xs"
                      >
                        -
                      </button>
                      <span className="text-xs font-bold text-white px-1">
                        {t.quantity}
                      </span>
                      <button
                        onClick={() => handleUpdateQuantity(t.item.id, 1)}
                        className="text-slate-400 hover:text-white font-bold text-xs"
                      >
                        +
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800">
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Order Notes (Optional)..."
              className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white placeholder-slate-500 text-xs focus:outline-none"
            />
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-slate-800">
          <div className="flex justify-between items-center mb-4">
            <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">
              Total Amount
            </span>
            <span className="text-xl font-extrabold text-amber-400">
              ₹{calculateTotal().toFixed(2)}
            </span>
          </div>

          <button
            onClick={handleSubmit}
            disabled={isSubmitting || ticketItems.length === 0}
            className="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs shadow-lg transition-all disabled:opacity-50"
          >
            {isSubmitting ? 'Submitting Order...' : 'Submit Order to Kitchen'}
          </button>
        </div>
      </div>
    </div>
  );
};
