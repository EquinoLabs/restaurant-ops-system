import React from 'react';
import { Order, OrderStatus } from '../../types/orders';

interface ActiveOrdersQueueProps {
  orders: Order[];
  onUpdateStatus: (orderId: string, status: OrderStatus) => Promise<void>;
  loading: boolean;
}

export const ActiveOrdersQueue: React.FC<ActiveOrdersQueueProps> = ({
  orders,
  onUpdateStatus,
  loading,
}) => {
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

  const activeOrders = orders.filter(
    (o) => o.status !== 'completed' && o.status !== 'cancelled'
  );

  return (
    <div className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6">
      <div className="pb-4 border-b border-slate-800 mb-6 flex justify-between items-center">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center space-x-2">
            <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <span>Active Orders Queue ({activeOrders.length})</span>
          </h2>
          <p className="text-xs text-slate-400">
            Track live preparation and service progress for dining tables
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
          {activeOrders.map((order) => (
            <div
              key={order.id}
              className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl flex flex-col justify-between"
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
                        {order.table_number || 'N/A'}
                      </span>
                    </div>
                  </div>
                  {getStatusBadge(order.status)}
                </div>

                <div className="mt-3 text-[11px] text-slate-400 flex justify-between">
                  <span>Waiter: {order.waiter_name || 'Staff'}</span>
                  <span>{new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>

                {/* Items */}
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
                  <span className="text-slate-400">Total</span>
                  <span className="text-sm font-extrabold text-amber-400">
                    ₹{Number(order.total_amount).toFixed(2)}
                  </span>
                </div>

                {/* Status action buttons */}
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
                  {order.status === 'served' && (
                    <button
                      onClick={() => onUpdateStatus(order.id, 'completed')}
                      className="col-span-2 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-slate-950 text-xs font-extrabold transition-colors"
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
          ))}
        </div>
      )}
    </div>
  );
};
