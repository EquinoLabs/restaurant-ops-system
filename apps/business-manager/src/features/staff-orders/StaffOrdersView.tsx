import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import { DiningTable, Order, OrderPayload, OrderStatus, PaymentMethod } from '@roms/shared-types';
import { AdminMenuCategory } from '@roms/shared-types';
import {
  fetchOutletTables,
  fetchOutletOrders,
  fetchAdminMenu,
  createOrder,
  updateOrderStatus,
  settleOrder,
} from '@roms/api-client';
import { TableSelectorGrid } from './TableSelectorGrid';
import { OrderEntryPanel } from './OrderEntryPanel';
import { ActiveOrdersQueue } from './ActiveOrdersQueue';

export const StaffOrdersView: React.FC = () => {
  const { token, user, selectedOutlet, setSelectedOutletId, logout } = useAuth();
  const navigate = useNavigate();

  const [tables, setTables] = useState<DiningTable[]>([]);
  const [selectedTable, setSelectedTable] = useState<DiningTable | null>(null);
  const [categories, setCategories] = useState<AdminMenuCategory[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'NEW_ORDER' | 'ACTIVE_ORDERS'>('NEW_ORDER');
  const [error, setError] = useState<string | null>(null);

  const isManagerOrOwner =
    selectedOutlet?.role === 'owner' || selectedOutlet?.role === 'manager';

  const loadData = useCallback(async () => {
    if (!token || !selectedOutlet) return;
    try {
      setLoading(true);
      setError(null);
      const [tableList, menu, orderList] = await Promise.all([
        fetchOutletTables(selectedOutlet.outlet_id, token),
        fetchAdminMenu(selectedOutlet.outlet_id, token),
        fetchOutletOrders(selectedOutlet.outlet_id, token),
      ]);
      setTables(tableList);
      setCategories(menu.categories);
      setOrders(orderList);
      if (tableList.length > 0 && !selectedTable) {
        setSelectedTable(tableList[0]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load POS order management data.');
    } finally {
      setLoading(false);
    }
  }, [token, selectedOutlet]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleOrderSubmitted = async (payload: OrderPayload) => {
    if (!token || !selectedOutlet) return;
    await createOrder(selectedOutlet.outlet_id, payload, token);
    await loadData();
    setActiveTab('ACTIVE_ORDERS');
  };

  const handleUpdateStatus = async (orderId: string, status: OrderStatus) => {
    if (!token) return;
    await updateOrderStatus(orderId, status, token);
    await loadData();
  };

  const handleSettleOrder = async (orderId: string, method: PaymentMethod) => {
    if (!token) return;
    setError(null);
    try {
      await settleOrder(orderId, { payment_method: method, confirm: true }, token);
      await loadData();
    } catch (err: any) {
      setError(err.message || 'Failed to settle order bill.');
      throw err;
    }
  };

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  if (loading && tables.length === 0) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-300">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-12 h-12 border-4 border-amber-500/20 border-t-amber-500 rounded-full animate-spin"></div>
          <p className="text-sm font-medium">Loading POS Staff Orders...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans pb-16">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 bg-slate-900/90 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 text-amber-400 font-extrabold text-lg tracking-tight">
              <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
                <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <span className="hidden sm:inline">ROMS POS</span>
            </div>

            {/* Outlet Selector Dropdown */}
            {user && user.memberships.length > 0 && (
              <select
                value={selectedOutlet?.outlet_id || ''}
                onChange={(e) => setSelectedOutletId(e.target.value)}
                className="bg-slate-800 border border-slate-700 text-white text-xs font-semibold rounded-xl px-3 py-2 pr-8 focus:outline-none focus:ring-2 focus:ring-amber-500/50 cursor-pointer"
              >
                {user.memberships.map((m) => (
                  <option key={m.outlet_id} value={m.outlet_id}>
                    {m.outlet_name} ({m.role.toUpperCase()})
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="flex items-center space-x-3">
            <Link
              to="/admin/kds"
              className="flex items-center space-x-1 px-3 py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 text-xs font-bold transition-colors"
            >
              <span>Kitchen Board</span>
            </Link>

            <Link
              to="/admin/tables"
              className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              Tables
            </Link>

            <Link
              to="/admin/menu"
              className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              Menu Admin
            </Link>

            <div className="h-4 w-px bg-slate-800"></div>

            <div className="flex items-center space-x-2">
              <div className="hidden lg:block text-right">
                <div className="text-xs font-bold text-white">{user?.display_name}</div>
                <div className="text-[10px] text-slate-400">{user?.email}</div>
              </div>
              <button
                onClick={handleSignOut}
                className="p-2 rounded-xl text-slate-400 hover:text-red-400 hover:bg-slate-800 transition-colors"
                title="Sign Out"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8">
        {error && (
          <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* View Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
          <div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">
              {selectedOutlet?.outlet_name} — Staff Order Entry
            </h1>
            <p className="mt-1 text-xs text-slate-400">
              Create table orders, snapshot menu prices, and track live order progress
            </p>
          </div>

          {/* Navigation Tabs */}
          <div className="flex rounded-xl bg-slate-900 p-1 border border-slate-800">
            <button
              onClick={() => setActiveTab('NEW_ORDER')}
              className={`px-4 py-2 text-xs font-bold rounded-lg transition-colors ${
                activeTab === 'NEW_ORDER'
                  ? 'bg-amber-500 text-slate-950 shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              + New Table Order
            </button>
            <button
              onClick={() => setActiveTab('ACTIVE_ORDERS')}
              className={`px-4 py-2 text-xs font-bold rounded-lg transition-colors ${
                activeTab === 'ACTIVE_ORDERS'
                  ? 'bg-amber-500 text-slate-950 shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Active Orders Queue ({orders.filter((o) => o.status !== 'completed' && o.status !== 'cancelled').length})
            </button>
          </div>
        </div>

        {/* Tab Content */}
        <div className="mt-8 space-y-8">
          {activeTab === 'NEW_ORDER' ? (
            <>
              {/* Tables Map */}
              <TableSelectorGrid
                tables={tables}
                selectedTableId={selectedTable?.id || null}
                onSelectTable={(table) => setSelectedTable(table)}
                isManagerOrOwner={isManagerOrOwner}
              />

              {/* Order Builder */}
              <OrderEntryPanel
                selectedTable={selectedTable}
                categories={categories}
                onOrderSubmitted={handleOrderSubmitted}
              />
            </>
          ) : (
            <ActiveOrdersQueue
              orders={orders}
              onUpdateStatus={handleUpdateStatus}
              onSettleOrder={handleSettleOrder}
              loading={loading}
            />
          )}
        </div>
      </main>
    </div>
  );
};
