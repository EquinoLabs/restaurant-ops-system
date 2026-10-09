import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../authentication/AuthContext';
import {
  AdminOutletMenu,
  AdminMenuCategory,
  AdminMenuItem,
  AuditLogItem,
  CategoryPayload,
  ItemPayload,
} from '../../types/adminMenu';
import {
  fetchAdminMenu,
  createCategory,
  updateCategory,
  createMenuItem,
  updateMenuItem,
  toggleItemAvailability,
  fetchAuditLogs,
  uploadItemImage,
  deleteItemImage,
} from '../../api/client';

import { CategoryEditorModal } from './CategoryEditorModal';
import { ItemEditorModal } from './ItemEditorModal';
import { AuditHistoryPanel } from './AuditHistoryPanel';

export const MenuAdminView: React.FC = () => {
  const { token, user, selectedOutlet, setSelectedOutletId, logout } = useAuth();
  const navigate = useNavigate();

  const [menuData, setMenuData] = useState<AdminOutletMenu | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [auditLoading, setAuditLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState('');
  const [availabilityFilter, setAvailabilityFilter] = useState<'ALL' | 'AVAILABLE' | 'UNAVAILABLE'>('ALL');

  // Modals state
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<AdminMenuCategory | null>(null);

  const [isItemModalOpen, setIsItemModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<AdminMenuItem | null>(null);
  const [targetCatIdForItem, setTargetCatIdForItem] = useState<string | undefined>(undefined);

  const [isAuditPanelOpen, setIsAuditPanelOpen] = useState(false);

  const loadMenuData = useCallback(async () => {
    if (!token || !selectedOutlet) return;
    try {
      setLoading(true);
      setError(null);
      const data = await fetchAdminMenu(selectedOutlet.outlet_id, token);
      setMenuData(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load administrative menu.');
    } finally {
      setLoading(false);
    }
  }, [token, selectedOutlet]);

  useEffect(() => {
    loadMenuData();
  }, [loadMenuData]);

  const loadAuditHistory = async () => {
    if (!token || !selectedOutlet) return;
    try {
      setAuditLoading(true);
      const logs = await fetchAuditLogs(selectedOutlet.outlet_id, token);
      setAuditLogs(logs);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setAuditLoading(false);
    }
  };

  const handleOpenAuditPanel = () => {
    setIsAuditPanelOpen(true);
    loadAuditHistory();
  };

  // Category Actions
  const handleSaveCategory = async (payload: CategoryPayload) => {
    if (!token || !selectedOutlet) return;
    if (editingCategory) {
      await updateCategory(editingCategory.id, payload, token);
    } else {
      await createCategory(selectedOutlet.outlet_id, payload, token);
    }
    await loadMenuData();
  };

  // Item Actions
  const handleSaveItem = async (payload: ItemPayload) => {
    if (!token || !selectedOutlet) return;
    if (editingItem) {
      await updateMenuItem(editingItem.id, payload, token);
    } else {
      await createMenuItem(selectedOutlet.outlet_id, payload, token);
    }
    await loadMenuData();
  };

  const handleUploadItemImage = async (file: File) => {
    if (!token || !selectedOutlet || !editingItem) return;
    const updated = await uploadItemImage(selectedOutlet.outlet_id, editingItem.id, file, token);
    setEditingItem(updated);
    await loadMenuData();
  };

  const handleDeleteItemImage = async () => {
    if (!token || !selectedOutlet || !editingItem) return;
    const updated = await deleteItemImage(selectedOutlet.outlet_id, editingItem.id, token);
    setEditingItem(updated);
    await loadMenuData();
  };


  const handleToggleAvailability = async (item: AdminMenuItem) => {
    if (!token) return;
    try {
      // Optimistic UI update
      setMenuData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          categories: prev.categories.map((cat) => ({
            ...cat,
            items: cat.items.map((i) =>
              i.id === item.id ? { ...i, is_available: !item.is_available } : i
            ),
          })),
        };
      });
      await toggleItemAvailability(item.id, !item.is_available, token);
    } catch (err) {
      console.error('Failed to toggle availability:', err);
      await loadMenuData();
    }
  };

  const handleSignOut = () => {
    logout();
    navigate('/login');
  };

  const isManagerOrOwner = selectedOutlet?.role === 'owner' || selectedOutlet?.role === 'manager';

  if (loading && !menuData) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-300">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-12 h-12 border-4 border-amber-500/20 border-t-amber-500 rounded-full animate-spin"></div>
          <p className="text-sm font-medium">Loading Menu Management Console...</p>
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
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              <span className="hidden sm:inline">ROMS Admin</span>
            </div>

            {/* Outlet Selector Dropdown */}
            {user && user.memberships.length > 0 && (
              <div className="relative">
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
              </div>
            )}
          </div>

          {/* User Controls & Actions */}
          <div className="flex items-center space-x-3">
            {user?.is_platform_admin && (
              <Link
                to="/platform"
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-xs font-bold transition-colors"
              >
                <span>Platform Admin</span>
              </Link>
            )}

            <Link
              to="/staff/orders"
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 text-xs font-bold transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <span>POS Orders</span>
            </Link>


            <button
              onClick={handleOpenAuditPanel}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
              title="Audit Logs"
            >
              <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="hidden md:inline">Audit Trail</span>
            </button>

            {menuData && (
              <a
                href={`/m/${menuData.public_slug}`}
                target="_blank"
                rel="noreferrer"
                className="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-semibold transition-colors"
              >
                <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                <span>Live Menu</span>
              </a>
            )}

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

        {/* Dashboard Title & Quick Actions Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-6 border-b border-slate-800">
          <div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">
              {menuData?.outlet_name || 'Outlet Menu Admin'}
            </h1>
            <p className="mt-1 text-xs text-slate-400">
              Manage categories, prices, item availability, and display order in real-time
            </p>
          </div>

          {isManagerOrOwner && (
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={() => {
                  setEditingCategory(null);
                  setIsCategoryModalOpen(true);
                }}
                className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-amber-400 text-xs font-bold transition-all flex items-center space-x-1.5 shadow-sm"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                </svg>
                <span>New Category</span>
              </button>

              <button
                onClick={() => {
                  setEditingItem(null);
                  setTargetCatIdForItem(undefined);
                  setIsItemModalOpen(true);
                }}
                className="px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-all flex items-center space-x-1.5 shadow-lg shadow-amber-500/15"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                </svg>
                <span>Add Menu Item</span>
              </button>
            </div>
          )}
        </div>

        {/* Search & Availability Filter Controls */}
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="sm:col-span-2 relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search items by name or description..."
              className="w-full px-4 py-2.5 pl-10 rounded-xl bg-slate-900 border border-slate-800 text-white placeholder-slate-500 text-xs focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
            <svg
              className="w-4 h-4 text-slate-500 absolute left-3.5 top-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          <div className="flex rounded-xl bg-slate-900 p-1 border border-slate-800">
            <button
              onClick={() => setAvailabilityFilter('ALL')}
              className={`flex-1 py-1.5 text-[11px] font-semibold rounded-lg transition-colors ${
                availabilityFilter === 'ALL' ? 'bg-amber-500 text-slate-950' : 'text-slate-400 hover:text-white'
              }`}
            >
              All Items
            </button>
            <button
              onClick={() => setAvailabilityFilter('AVAILABLE')}
              className={`flex-1 py-1.5 text-[11px] font-semibold rounded-lg transition-colors ${
                availabilityFilter === 'AVAILABLE' ? 'bg-emerald-500 text-slate-950' : 'text-slate-400 hover:text-white'
              }`}
            >
              In Stock
            </button>
            <button
              onClick={() => setAvailabilityFilter('UNAVAILABLE')}
              className={`flex-1 py-1.5 text-[11px] font-semibold rounded-lg transition-colors ${
                availabilityFilter === 'UNAVAILABLE' ? 'bg-red-500 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Out of Stock
            </button>
          </div>
        </div>

        {/* Menu Categories & Items List */}
        <div className="mt-8 space-y-8">
          {menuData?.categories.map((cat) => {
            const filteredItems = cat.items.filter((item) => {
              const matchesSearch =
                item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                (item.description && item.description.toLowerCase().includes(searchQuery.toLowerCase()));
              const matchesFilter =
                availabilityFilter === 'ALL'
                  ? true
                  : availabilityFilter === 'AVAILABLE'
                  ? item.is_available
                  : !item.is_available;
              return matchesSearch && matchesFilter;
            });

            if (searchQuery && filteredItems.length === 0) return null;

            return (
              <section key={cat.id} className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6">
                {/* Category Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-slate-800">
                  <div className="flex items-center space-x-3">
                    <h2 className="text-lg font-bold text-white">{cat.name}</h2>
                    {!cat.is_active && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-700 text-slate-300 uppercase">
                        Archived
                      </span>
                    )}
                    <span className="text-xs text-slate-500 font-mono">
                      Order: {cat.sort_order}
                    </span>
                  </div>

                  {isManagerOrOwner && (
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => {
                          setEditingCategory(cat);
                          setIsCategoryModalOpen(true);
                        }}
                        className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-colors"
                      >
                        Edit Category
                      </button>
                      <button
                        onClick={() => {
                          setEditingItem(null);
                          setTargetCatIdForItem(cat.id);
                          setIsItemModalOpen(true);
                        }}
                        className="px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 text-xs font-semibold border border-amber-500/30 transition-colors"
                      >
                        + Add Item
                      </button>
                    </div>
                  )}
                </div>

                {cat.description && (
                  <p className="mt-2 text-xs text-slate-400">{cat.description}</p>
                )}

                {/* Items List */}
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {filteredItems.map((item) => (
                    <div
                      key={item.id}
                      className={`p-4 rounded-xl border transition-all flex flex-col justify-between ${
                        !item.is_available
                          ? 'bg-slate-900/40 border-slate-800/80 opacity-80'
                          : 'bg-slate-800/60 border-slate-700/60 hover:border-slate-600'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h3 className="text-sm font-bold text-white">{item.name}</h3>
                            {!item.is_active && (
                              <span className="text-[9px] px-1.5 py-0.5 bg-slate-800 text-slate-400 rounded">
                                Archived
                              </span>
                            )}
                          </div>
                          {item.description && (
                            <p className="mt-1 text-xs text-slate-400 line-clamp-2">
                              {item.description}
                            </p>
                          )}
                        </div>

                        <div className="text-right">
                          <span className="text-sm font-extrabold text-amber-400">
                            ₹{Number(item.price).toFixed(2)}
                          </span>
                        </div>
                      </div>

                      {/* Quick Item Actions & Availability Toggle */}
                      <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                        <button
                          onClick={() => handleToggleAvailability(item)}
                          className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                            item.is_available
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20'
                              : 'bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20'
                          }`}
                        >
                          <span
                            className={`w-2 h-2 rounded-full ${
                              item.is_available ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
                            }`}
                          ></span>
                          <span>{item.is_available ? 'In Stock' : 'Out of Stock'}</span>
                        </button>

                        {isManagerOrOwner && (
                          <button
                            onClick={() => {
                              setEditingItem(item);
                              setIsItemModalOpen(true);
                            }}
                            className="px-2.5 py-1 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-slate-700/60 transition-colors"
                          >
                            Edit Item
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      </main>

      {/* Category Editor Modal */}
      <CategoryEditorModal
        isOpen={isCategoryModalOpen}
        onClose={() => setIsCategoryModalOpen(false)}
        onSave={handleSaveCategory}
        category={editingCategory}
      />

      {/* Item Editor Modal */}
      <ItemEditorModal
        isOpen={isItemModalOpen}
        onClose={() => setIsItemModalOpen(false)}
        onSave={handleSaveItem}
        categories={menuData?.categories || []}
        item={editingItem}
        defaultCategoryId={targetCatIdForItem}
        currency={menuData?.currency}
        onUploadImage={editingItem ? handleUploadItemImage : undefined}
        onDeleteImage={editingItem ? handleDeleteItemImage : undefined}
      />


      {/* Audit History Panel */}
      <AuditHistoryPanel
        isOpen={isAuditPanelOpen}
        onClose={() => setIsAuditPanelOpen(false)}
        logs={auditLogs}
        loading={auditLoading}
      />
    </div>
  );
};
