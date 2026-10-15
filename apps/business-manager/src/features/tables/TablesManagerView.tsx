import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '@roms/api-client';
import { DiningTable, TableUpdatePayload } from '@roms/shared-types';
import { fetchOutletTables, createTable, updateTable } from '@roms/api-client';
import { TableEditorModal } from './TableEditorModal';

export const TablesManagerView: React.FC = () => {
  const { token, user, selectedOutlet, setSelectedOutletId, logout } = useAuth();
  const navigate = useNavigate();

  const [tables, setTables] = useState<DiningTable[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTable, setEditingTable] = useState<DiningTable | null>(null);

  const isManagerOrOwner =
    selectedOutlet?.role === 'owner' || selectedOutlet?.role === 'manager';

  const loadTables = useCallback(async () => {
    if (!token || !selectedOutlet) return;
    try {
      setLoading(true);
      setError(null);
      const list = await fetchOutletTables(selectedOutlet.outlet_id, token);
      setTables(list);
    } catch (err: any) {
      setError(err.message || 'Failed to load dining tables.');
    } finally {
      setLoading(false);
    }
  }, [token, selectedOutlet]);

  useEffect(() => {
    loadTables();
  }, [loadTables]);

  const handleOpenCreate = () => {
    setEditingTable(null);
    setModalOpen(true);
  };

  const handleOpenEdit = (table: DiningTable) => {
    setEditingTable(table);
    setModalOpen(true);
  };

  const handleSave = async (payload: TableUpdatePayload) => {
    if (!token || !selectedOutlet) return;
    if (editingTable) {
      await updateTable(editingTable.id, payload, token);
    } else {
      await createTable(selectedOutlet.outlet_id, payload.table_number!, payload.capacity ?? 4, token);
    }
    await loadTables();
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
          <p className="text-sm font-medium">Loading Dining Tables...</p>
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
              <span className="hidden sm:inline">ROMS Tables</span>
            </div>

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
              to="/admin/menu"
              className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              Menu Admin
            </Link>
            <Link
              to="/staff/orders"
              className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              POS Orders
            </Link>
            <Link
              to="/admin/kds"
              className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              Kitchen Board
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
              {selectedOutlet?.outlet_name} — Dining Tables
            </h1>
            <p className="mt-1 text-xs text-slate-400">
              {isManagerOrOwner
                ? 'Create tables and manage seat capacity and availability status'
                : 'Read-only view of dining tables for this outlet'}
            </p>
          </div>

          {isManagerOrOwner && (
            <button
              onClick={handleOpenCreate}
              className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-all flex items-center space-x-1 self-start sm:self-auto"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              <span>+ Add Table</span>
            </button>
          )}
        </div>

        {/* Tables Grid */}
        <div className="mt-8">
          {tables.length === 0 && !loading ? (
            <div className="bg-slate-900/60 rounded-2xl border border-slate-800 p-12 text-center">
              <p className="text-slate-400 text-sm font-medium">No dining tables yet.</p>
              {isManagerOrOwner && (
                <button
                  onClick={handleOpenCreate}
                  className="mt-4 px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-all"
                >
                  Create the first table
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {tables.map((table) => (
                <div
                  key={table.id}
                  className="bg-slate-900/60 rounded-2xl border border-slate-800 p-5 flex flex-col justify-between"
                >
                  <div className="flex items-start justify-between">
                    <span className="text-lg font-extrabold text-white tracking-tight">
                      {table.table_number}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        table.status === 'available'
                          ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                          : table.status === 'occupied'
                          ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                          : 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                      }`}
                    >
                      {table.status.charAt(0).toUpperCase() + table.status.slice(1)}
                    </span>
                  </div>
                  <div className="mt-4 flex items-center justify-between text-xs text-slate-400 font-medium">
                    <span>Seats: {table.capacity}</span>
                    {isManagerOrOwner && (
                      <button
                        onClick={() => handleOpenEdit(table)}
                        className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-amber-400 text-[11px] font-bold transition-colors"
                      >
                        Edit
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Create / Edit Modal */}
      <TableEditorModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSave={handleSave}
        table={editingTable}
      />
    </div>
  );
};
