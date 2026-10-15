import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import { Order, OrderStatus } from '@roms/shared-types';
import { fetchOutletOrders, updateOrderStatus } from '@roms/api-client';
import { KDSTicketCard } from './KDSTicketCard';

type KDSFilter = 'ALL_KITCHEN' | 'IN_PREP' | 'READY' | 'ALL_ACTIVE';

export const KDSView: React.FC = () => {
  const { token, user, selectedOutlet, setSelectedOutletId, logout } = useAuth();
  const navigate = useNavigate();

  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [submittingOrderIds, setSubmittingOrderIds] = useState<Set<string>>(new Set());
  
  // Filter tab
  const [filterTab, setFilterTab] = useState<KDSFilter>('ALL_KITCHEN');

  // Auto-refresh settings
  const [autoRefreshSec, setAutoRefreshSec] = useState<number>(10);
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);

  // Audio alerts setting (Web Audio API)
  const [soundEnabled, setSoundEnabled] = useState<boolean>(false);
  const audioCtxRef = useRef<AudioContext | null>(null);

  // New-order ID tracking refs
  const knownKitchenOrderIdsRef = useRef<Set<string>>(new Set());
  const isInitialLoadRef = useRef<boolean>(true);
  const prevOutletIdRef = useRef<string | null>(null);

  // Synchronized elapsed timer clock
  const [now, setNow] = useState<number>(Date.now());

  // Request version counter for stale-response protection & in-flight polling guard
  const requestVersionRef = useRef<number>(0);
  const inFlightPollingRef = useRef<boolean>(false);

  // Clock tick interval (every 1 second)
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Web Audio API notification chime generator
  const playAudioChime = useCallback(() => {
    try {
      if (!audioCtxRef.current) {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        if (AudioContextClass) {
          audioCtxRef.current = new AudioContextClass();
        }
      }

      if (audioCtxRef.current && audioCtxRef.current.state === 'suspended') {
        audioCtxRef.current.resume();
      }

      if (audioCtxRef.current) {
        const ctx = audioCtxRef.current;
        const nowTime = ctx.currentTime;

        // Double-beep kitchen chime (880Hz -> 1174.66Hz)
        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(880, nowTime); // A5
        gain1.gain.setValueAtTime(0.15, nowTime);
        gain1.gain.exponentialRampToValueAtTime(0.001, nowTime + 0.15);
        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start(nowTime);
        osc1.stop(nowTime + 0.15);

        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(1174.66, nowTime + 0.2); // D6
        gain2.gain.setValueAtTime(0.2, nowTime + 0.2);
        gain2.gain.exponentialRampToValueAtTime(0.001, nowTime + 0.4);
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(nowTime + 0.2);
        osc2.stop(nowTime + 0.4);
      }
    } catch (err) {
      console.warn('Kitchen Audio Chime notice:', err);
    }
  }, []);

  const toggleSound = () => {
    const nextSoundState = !soundEnabled;
    setSoundEnabled(nextSoundState);
    if (nextSoundState) {
      // Test chime when enabling audio
      playAudioChime();
    }
  };

  // Main data load function
  const loadOrders = useCallback(async (isSilent = false) => {
    if (!token || !selectedOutlet) return;
    if (inFlightPollingRef.current) return;

    const currentReqVersion = ++requestVersionRef.current;

    try {
      inFlightPollingRef.current = true;
      setIsPolling(true);
      if (!isSilent) setError(null);

      const fetchedOrders = await fetchOutletOrders(selectedOutlet.outlet_id, token);

      // Stale-response guard: If a newer fetch or mutation occurred after this request started, discard response.
      if (currentReqVersion < requestVersionRef.current) {
        return;
      }
      
      // Extract active kitchen orders (confirmed & in_kitchen)
      const activeKitchenOrders = fetchedOrders.filter(
        (o) => o.status === 'confirmed' || o.status === 'in_kitchen'
      );
      const activeKitchenOrderIds = new Set(activeKitchenOrders.map((o) => o.id));

      if (isInitialLoadRef.current) {
        knownKitchenOrderIdsRef.current = activeKitchenOrderIds;
        isInitialLoadRef.current = false;
      } else {
        const hasNewOrder = activeKitchenOrders.some((o) => !knownKitchenOrderIdsRef.current.has(o.id));
        if (soundEnabled && hasNewOrder) {
          playAudioChime();
        }
        knownKitchenOrderIdsRef.current = activeKitchenOrderIds;
      }

      setOrders(fetchedOrders);
      setLastRefreshedAt(new Date());
    } catch (err: any) {
      if (currentReqVersion < requestVersionRef.current) return;
      if (!isSilent) {
        setError(err.message || 'Failed to refresh kitchen orders.');
      }
    } finally {
      if (currentReqVersion === requestVersionRef.current) {
        setIsPolling(false);
        setLoading(false);
        inFlightPollingRef.current = false;
      }
    }
  }, [token, selectedOutlet, soundEnabled, playAudioChime]);

  // Initial load and outlet change tracking
  useEffect(() => {
    if (!selectedOutlet) return;

    if (prevOutletIdRef.current !== selectedOutlet.outlet_id) {
      prevOutletIdRef.current = selectedOutlet.outlet_id;
      isInitialLoadRef.current = true;
      knownKitchenOrderIdsRef.current = new Set();
      requestVersionRef.current++; // Invalidate any in-flight requests from the previous outlet
      setOrders([]);
      setLoading(true);
    }

    loadOrders(false);
  }, [selectedOutlet, loadOrders]);

  // Polling loop effect
  useEffect(() => {
    if (autoRefreshSec <= 0 || !token || !selectedOutlet) return;

    const interval = setInterval(() => {
      loadOrders(true);
    }, autoRefreshSec * 1000);

    return () => clearInterval(interval);
  }, [autoRefreshSec, token, selectedOutlet, loadOrders]);

  // Handle order status transitions
  const handleUpdateStatus = async (orderId: string, targetStatus: OrderStatus) => {
    if (!token) return;

    setSubmittingOrderIds((prev) => new Set(prev).add(orderId));
    setError(null);

    try {
      const updatedOrder = await updateOrderStatus(orderId, targetStatus, token);

      // Advance request version to invalidate any stale GET requests initiated before/during this mutation
      requestVersionRef.current++;

      // Immediately reconcile local orders state with server-confirmed mutation response
      setOrders((prevOrders) =>
        prevOrders.map((o) => (o.id === updatedOrder.id ? updatedOrder : o))
      );

      // Update active kitchen order IDs tracking set
      if (updatedOrder.status === 'confirmed' || updatedOrder.status === 'in_kitchen') {
        knownKitchenOrderIdsRef.current.add(updatedOrder.id);
      } else {
        knownKitchenOrderIdsRef.current.delete(updatedOrder.id);
      }

      // Reset in-flight lock and trigger a fresh background pull
      inFlightPollingRef.current = false;
      await loadOrders(true);
    } catch (err: any) {
      setError(err.message || `Failed to update order status to ${targetStatus}`);
    } finally {
      setSubmittingOrderIds((prev) => {
        const next = new Set(prev);
        next.delete(orderId);
        return next;
      });
    }
  };

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  // Filter orders according to tab selection
  const filteredOrders = orders.filter((o) => {
    if (filterTab === 'ALL_KITCHEN') {
      return o.status === 'confirmed' || o.status === 'in_kitchen';
    }
    if (filterTab === 'IN_PREP') {
      return o.status === 'in_kitchen';
    }
    if (filterTab === 'READY') {
      return o.status === 'served';
    }
    if (filterTab === 'ALL_ACTIVE') {
      return o.status !== 'completed' && o.status !== 'cancelled';
    }
    return true;
  });

  const kitchenCount = orders.filter((o) => o.status === 'confirmed' || o.status === 'in_kitchen').length;
  const readyCount = orders.filter((o) => o.status === 'served').length;
  const pendingCount = orders.filter((o) => o.status === 'pending').length;


  if (loading && orders.length === 0) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-300">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-12 h-12 border-4 border-amber-500/20 border-t-amber-500 rounded-full animate-spin"></div>
          <p className="text-sm font-medium">Connecting to Kitchen Display System...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans pb-12">
      {/* KDS Header Toolbar */}
      <header className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Brand & Outlet Selector */}
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 text-amber-400 font-black text-lg tracking-tight">
              <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center">
                <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </div>
              <span className="hidden md:inline uppercase tracking-wider text-sm">ROMS KDS</span>
            </div>

            {user && user.memberships.length > 0 && (
              <select
                value={selectedOutlet?.outlet_id || ''}
                onChange={(e) => setSelectedOutletId(e.target.value)}
                className="bg-slate-800 border border-slate-700 text-white text-xs font-bold rounded-xl px-3 py-2 pr-8 focus:outline-none focus:ring-2 focus:ring-amber-500/50 cursor-pointer"
              >
                {user.memberships.map((m) => (
                  <option key={m.outlet_id} value={m.outlet_id}>
                    {m.outlet_name} ({m.role.toUpperCase()})
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Quick Metrics & Polling Controls */}
          <div className="flex items-center space-x-3">
            {/* Polling status & Refresh button */}
            <div className="hidden sm:flex items-center space-x-2 bg-slate-800/80 px-3 py-1.5 rounded-xl border border-slate-700/80 text-xs">
              <span
                className={`w-2 h-2 rounded-full ${
                  isPolling ? 'bg-amber-400 animate-ping' : 'bg-emerald-400'
                }`}
              ></span>
              <span className="text-slate-300 font-mono text-[11px]">
                {lastRefreshedAt ? lastRefreshedAt.toLocaleTimeString() : 'Live'}
              </span>

              <button
                onClick={() => loadOrders(false)}
                disabled={isPolling}
                className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                title="Manual Refresh"
              >
                <svg
                  className={`w-4 h-4 ${isPolling ? 'animate-spin text-amber-400' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>

            {/* Auto Refresh Interval Dropdown */}
            <select
              value={autoRefreshSec}
              onChange={(e) => setAutoRefreshSec(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 text-slate-300 text-xs font-semibold rounded-xl px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-amber-500/50 cursor-pointer"
              title="Auto-refresh Interval"
            >
              <option value={10}>Refresh: 10s</option>
              <option value={30}>Refresh: 30s</option>
              <option value={0}>Refresh: Off</option>
            </select>

            {/* Audio Toggle */}
            <button
              onClick={toggleSound}
              className={`p-2 rounded-xl border text-xs font-bold transition-all flex items-center space-x-1.5 ${
                soundEnabled
                  ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                  : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'
              }`}
              title={soundEnabled ? 'Kitchen Chime Active' : 'Sound Muted'}
            >
              {soundEnabled ? (
                <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                </svg>
              )}
              <span className="hidden lg:inline">{soundEnabled ? 'Audio On' : 'Audio Off'}</span>
            </button>

            {/* Navigation Actions */}
            <Link
              to="/staff/orders"
              className="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              POS Orders
            </Link>

            <Link
              to="/admin/menu"
              className="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              Menu Admin
            </Link>

            <Link
              to="/admin/tables"
              className="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              Tables
            </Link>

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
      </header>

      {/* Main KDS Board Workspace */}
      <main className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        {error && (
          <div className="mb-6 p-4 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <svg className="w-5 h-5 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{error}</span>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-xs font-bold text-red-400 hover:text-red-300 underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* View Header & Queue Filter Tabs */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
          <div>
            <h1 className="text-2xl font-black text-white tracking-tight flex items-center space-x-3">
              <span>{selectedOutlet?.outlet_name} — Kitchen Board</span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-black bg-amber-500/20 text-amber-400 border border-amber-500/30">
                {kitchenCount} Active Ticket{kitchenCount !== 1 ? 's' : ''}
              </span>
              {pendingCount > 0 && (
                <span
                  className="px-2.5 py-0.5 rounded-full text-xs font-black bg-blue-500/20 text-blue-400 border border-blue-500/30"
                  title="Customer orders awaiting staff confirmation"
                >
                  Pending ({pendingCount})
                </span>
              )}
            </h1>
            <p className="mt-1 text-xs text-slate-400">
              Live preparation tickets, special instructions, and bump station status
            </p>
          </div>

          {/* Status Column Filter Tabs */}
          <div className="flex rounded-2xl bg-slate-900 p-1 border border-slate-800 text-xs font-extrabold">
            <button
              onClick={() => setFilterTab('ALL_KITCHEN')}
              className={`px-4 py-2 rounded-xl transition-all ${
                filterTab === 'ALL_KITCHEN'
                  ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Kitchen Queue ({kitchenCount})
            </button>
            <button
              onClick={() => setFilterTab('IN_PREP')}
              className={`px-4 py-2 rounded-xl transition-all ${
                filterTab === 'IN_PREP'
                  ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              In Prep ({orders.filter((o) => o.status === 'in_kitchen').length})
            </button>
            <button
              onClick={() => setFilterTab('READY')}
              className={`px-4 py-2 rounded-xl transition-all ${
                filterTab === 'READY'
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Ready ({readyCount})
            </button>
            <button
              onClick={() => setFilterTab('ALL_ACTIVE')}
              className={`px-4 py-2 rounded-xl transition-all ${
                filterTab === 'ALL_ACTIVE'
                  ? 'bg-slate-700 text-white shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              All Active ({orders.filter((o) => o.status !== 'completed' && o.status !== 'cancelled').length})
            </button>
          </div>
        </div>

        {/* Tickets Grid */}
        <div className="mt-6">
          {filteredOrders.length === 0 ? (
            <div className="py-20 flex flex-col items-center justify-center border-2 border-dashed border-slate-800 rounded-3xl bg-slate-900/30 text-center">
              <div className="w-16 h-16 rounded-2xl bg-slate-800/80 border border-slate-700 flex items-center justify-center text-slate-500 mb-4">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-slate-200">No Active Kitchen Tickets</h3>
              <p className="mt-1 text-xs text-slate-400 max-w-sm">
                New orders placed by waitstaff or customers will automatically appear here on the kitchen board.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {filteredOrders.map((order) => (
                <KDSTicketCard
                  key={order.id}
                  order={order}
                  onUpdateStatus={handleUpdateStatus}
                  isSubmitting={submittingOrderIds.has(order.id)}
                  now={now}
                />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
