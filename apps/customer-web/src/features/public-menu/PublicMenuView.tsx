import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { fetchPublicMenu, submitPublicOrder } from '@roms/api-client';
import { OutletPublicMenu, MenuItem } from '@roms/shared-types';
import { CartItem, Order, PublicOrderPayload } from '@roms/shared-types';
import { CategorySection } from './CategorySection';
import { MenuSkeleton } from './MenuSkeleton';
import { NotFoundView } from '@roms/ui';
import { Error500View } from './Error500View';
import { CartBottomBar } from './CartBottomBar';
import { CartDrawer } from './CartDrawer';
import { OrderConfirmationModal } from './OrderConfirmationModal';
import { Search, MapPin, Sparkles, QrCode, Download, X, UtensilsCrossed, ShoppingBag } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const PublicMenuView: React.FC = () => {
  const { publicSlug } = useParams<{ publicSlug: string }>();
  const [searchParams] = useSearchParams();
  const tableParam = searchParams.get('table')?.trim() || null;

  const [menuData, setMenuData] = useState<OutletPublicMenu | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeCategoryId, setActiveCategoryId] = useState<string | null>(null);
  const [showQrModal, setShowQrModal] = useState<boolean>(false);

  // Cart & Order state
  const [cart, setCart] = useState<Record<string, CartItem>>({});
  const [isCartOpen, setIsCartOpen] = useState<boolean>(false);
  const [orderNotes, setOrderNotes] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [confirmedOrder, setConfirmedOrder] = useState<Order | null>(null);
  const [inFlightIdempotencyKey, setInFlightIdempotencyKey] = useState<string | null>(null);

  const loadMenu = useCallback(() => {
    if (!publicSlug) {
      setError('OUTLET_NOT_FOUND');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    fetchPublicMenu(publicSlug)
      .then((data) => {
        setMenuData(data);
        if (data.categories.length > 0) {
          setActiveCategoryId(data.categories[0].id);
        }
      })
      .catch((err) => {
        setError(err.message || 'SERVER_ERROR');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [publicSlug]);

  useEffect(() => {
    loadMenu();
  }, [loadMenu]);

  // Search filtering logic
  const filteredCategories = useMemo(() => {
    if (!menuData) return [];
    if (!searchQuery.trim()) return menuData.categories;

    const query = searchQuery.toLowerCase().trim();
    return menuData.categories
      .map((cat) => ({
        ...cat,
        items: cat.items.filter(
          (item) =>
            item.name.toLowerCase().includes(query) ||
            (item.description && item.description.toLowerCase().includes(query))
        ),
      }))
      .filter((cat) => cat.items.length > 0);
  }, [menuData, searchQuery]);

  // Cart helpers & computed values
  const cartItems = useMemo(() => Object.values(cart), [cart]);

  const cartQuantities = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const item of cartItems) {
      counts[item.menu_item_id] = item.quantity;
    }
    return counts;
  }, [cartItems]);

  const totalItemsCount = useMemo(() => {
    return cartItems.reduce((acc, curr) => acc + curr.quantity, 0);
  }, [cartItems]);

  const totalEstimatedAmount = useMemo(() => {
    return cartItems.reduce((acc, curr) => acc + curr.price * curr.quantity, 0);
  }, [cartItems]);

  const handleAddToCart = (item: MenuItem) => {
    setCart((prev) => ({
      ...prev,
      [item.id]: {
        menu_item_id: item.id,
        name: item.name,
        price: item.price,
        quantity: 1,
        special_instructions: '',
        image_url: item.image_url,
      },
    }));
    setInFlightIdempotencyKey(null);
  };

  const handleIncrement = (itemId: string) => {
    setCart((prev) => {
      const existing = prev[itemId];
      if (!existing || existing.quantity >= 99) return prev;
      return {
        ...prev,
        [itemId]: { ...existing, quantity: existing.quantity + 1 },
      };
    });
    setInFlightIdempotencyKey(null);
  };

  const handleDecrement = (itemId: string) => {
    setCart((prev) => {
      const existing = prev[itemId];
      if (!existing) return prev;
      if (existing.quantity <= 1) {
        const updated = { ...prev };
        delete updated[itemId];
        return updated;
      }
      return {
        ...prev,
        [itemId]: { ...existing, quantity: existing.quantity - 1 },
      };
    });
    setInFlightIdempotencyKey(null);
  };

  const handleRemoveItem = (itemId: string) => {
    setCart((prev) => {
      const updated = { ...prev };
      delete updated[itemId];
      return updated;
    });
    setInFlightIdempotencyKey(null);
  };

  const handleUpdateInstructions = (itemId: string, instructions: string) => {
    setCart((prev) => {
      const existing = prev[itemId];
      if (!existing) return prev;
      return {
        ...prev,
        [itemId]: { ...existing, special_instructions: instructions },
      };
    });
    setInFlightIdempotencyKey(null);
  };

  const handleClearCart = () => {
    setCart({});
    setOrderNotes('');
    setInFlightIdempotencyKey(null);
    setSubmitError(null);
  };

  const handleSubmitOrder = async () => {
    if (!publicSlug || cartItems.length === 0 || isSubmitting) return;

    setIsSubmitting(true);
    setSubmitError(null);

    // Reuse existing in-flight idempotency key on retry, or generate a fresh UUID
    const key =
      inFlightIdempotencyKey ||
      (typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : 'idemp-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9));
    setInFlightIdempotencyKey(key);

    const payload: PublicOrderPayload = {
      table_number: tableParam || null,
      order_type: tableParam ? 'dine_in' : 'takeaway',
      items: cartItems.map((item) => ({
        menu_item_id: item.menu_item_id,
        quantity: item.quantity,
        special_instructions: item.special_instructions?.trim() || null,
      })),
      notes: orderNotes.trim() || null,
      idempotency_key: key,
    };

    try {
      const order = await submitPublicOrder(publicSlug, payload, key);
      setConfirmedOrder(order);
      setCart({});
      setOrderNotes('');
      setIsCartOpen(false);
      setInFlightIdempotencyKey(null);
      setSubmitError(null);
    } catch (err: any) {
      // Retain customer's cart on error for easy retry
      setSubmitError(err.message || 'Failed to place order. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) return <MenuSkeleton />;
  if (error === 'OUTLET_NOT_FOUND') {
    return <NotFoundView />;
  }
  if (error || !menuData) {
    return <Error500View onRetry={loadMenu} />;
  }

  const scrollToCategory = (categoryId: string) => {
    setActiveCategoryId(categoryId);
    const element = document.getElementById(`category-${categoryId}`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const qrImageUrl = `${API_BASE_URL}/public/outlets/${publicSlug}/qr`;
  const qrDownloadUrl = `${API_BASE_URL}/public/outlets/${publicSlug}/qr?download=true`;

  const primaryColor = menuData.primary_color || '#d97706'; // default amber-600

  return (
    <div className="max-w-md mx-auto min-h-screen bg-gray-50 pb-28 antialiased relative">
      {/* Cover Image Banner (Optional Outlet Branding) */}
      {menuData.cover_image_url && (
        <div className="h-36 w-full relative bg-slate-900 overflow-hidden">
          <img
            src={menuData.cover_image_url}
            alt={menuData.outlet_name}
            className="w-full h-full object-cover opacity-90"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent"></div>
        </div>
      )}

      {/* Outlet Header */}
      <header
        className={`bg-white border-b border-gray-100 p-5 sticky top-0 z-20 shadow-xs ${
          menuData.cover_image_url ? '-mt-6 rounded-t-2xl relative z-30 shadow-md' : ''
        }`}
      >
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-3">
            {menuData.logo_url && (
              <img
                src={menuData.logo_url}
                alt={`${menuData.outlet_name} Logo`}
                className="w-12 h-12 rounded-xl object-cover border border-gray-200/80 shadow-xs"
              />
            )}
            <div>
              <div
                className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider"
                style={{ color: primaryColor }}
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Digital Menu</span>
              </div>
              <h1 className="text-xl font-extrabold text-gray-900 tracking-tight leading-snug">
                {menuData.outlet_name}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Table / Takeaway Context Badge */}
            {tableParam ? (
              <div
                data-testid="header-table-badge"
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 text-emerald-800 text-xs font-bold rounded-lg border border-emerald-200 shadow-2xs mt-1"
                title={`Serving Table ${tableParam}`}
              >
                <UtensilsCrossed className="w-3.5 h-3.5 text-emerald-600" />
                <span>Table {tableParam}</span>
              </div>
            ) : (
              <div
                data-testid="header-takeaway-badge"
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-50 text-blue-800 text-xs font-bold rounded-lg border border-blue-200 shadow-2xs mt-1"
                title="Self Pickup / Takeaway"
              >
                <ShoppingBag className="w-3.5 h-3.5 text-blue-600" />
                <span>Takeaway</span>
              </div>
            )}

            <button
              onClick={() => setShowQrModal(true)}
              className="inline-flex items-center gap-1.5 px-2 py-1 bg-amber-50 hover:bg-amber-100 text-amber-800 text-xs font-medium rounded-lg border border-amber-200/80 transition-all flex-shrink-0 mt-1"
              title="View permanent table QR code"
            >
              <QrCode className="w-3.5 h-3.5 text-amber-600" />
              <span className="hidden xs:inline">QR Stand</span>
            </button>
          </div>
        </div>

        {menuData.address && (
          <div className="flex items-center gap-1.5 text-xs text-gray-500 mt-1">
            <MapPin className="w-3.5 h-3.5 flex-shrink-0 text-gray-400" />
            <span className="truncate">{menuData.address}</span>
          </div>
        )}

        {/* Search Bar */}
        <div className="mt-4 relative">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search menu items..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-gray-100/80 border border-transparent rounded-xl text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:bg-white focus:border-amber-400 transition-all"
          />
        </div>
      </header>

      {/* Category Pills Navigation (Sticky) */}
      {!searchQuery && menuData.categories.length > 0 && (
        <div className="sticky top-[141px] z-10 bg-white/95 backdrop-blur-md border-b border-gray-100 px-4 py-2.5 overflow-x-auto no-scrollbar flex gap-2">
          {menuData.categories.map((cat) => {
            const isActive = activeCategoryId === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => scrollToCategory(cat.id)}
                style={isActive ? { backgroundColor: primaryColor, color: '#ffffff' } : {}}
                className={`px-3.5 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all ${
                  isActive
                    ? 'shadow-sm'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200/70'
                }`}
              >
                {cat.name}
              </button>
            );
          })}
        </div>
      )}

      {/* Main Menu Categories Content */}
      <main className="p-4">
        {filteredCategories.length === 0 ? (
          <div className="text-center py-12 px-4">
            <p className="text-gray-500 text-sm">No items found matching "{searchQuery}"</p>
          </div>
        ) : (
          filteredCategories.map((category) => (
            <CategorySection
              key={category.id}
              category={category}
              currency={menuData.currency}
              cartQuantities={cartQuantities}
              onAddToCart={handleAddToCart}
              onIncrement={handleIncrement}
              onDecrement={handleDecrement}
              primaryColor={primaryColor}
            />
          ))
        )}
      </main>

      {/* Footer Branding */}
      <footer className="text-center py-6 border-t border-gray-200/60 text-xs text-gray-400">
        Powered by <span className="font-semibold text-gray-600">ROMS Digital Menu</span>
      </footer>

      {/* Sticky Bottom Cart Bar */}
      <CartBottomBar
        totalItems={totalItemsCount}
        totalAmount={totalEstimatedAmount}
        currency={menuData.currency}
        onOpenCart={() => setIsCartOpen(true)}
        primaryColor={primaryColor}
      />

      {/* Expandable Cart Drawer */}
      <CartDrawer
        isOpen={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        items={cartItems}
        currency={menuData.currency}
        tableNumber={tableParam}
        onIncrement={handleIncrement}
        onDecrement={handleDecrement}
        onRemoveItem={handleRemoveItem}
        onUpdateInstructions={handleUpdateInstructions}
        orderNotes={orderNotes}
        onChangeOrderNotes={setOrderNotes}
        onClearCart={handleClearCart}
        onSubmitOrder={handleSubmitOrder}
        isSubmitting={isSubmitting}
        submitError={submitError}
        onClearError={() => setSubmitError(null)}
        primaryColor={primaryColor}
      />

      {/* Order Confirmation Screen */}
      <OrderConfirmationModal
        order={confirmedOrder}
        currency={menuData.currency}
        onClose={() => setConfirmedOrder(null)}
        primaryColor={primaryColor}
      />

      {/* QR Code Printable Modal */}
      {showQrModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 animate-fade-in">
          <div className="bg-white rounded-2xl max-w-xs w-full p-6 text-center relative shadow-xl border border-gray-100">
            <button
              onClick={() => setShowQrModal(false)}
              className="absolute right-4 top-4 text-gray-400 hover:text-gray-600 p-1 rounded-full hover:bg-gray-100"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="inline-flex items-center gap-1.5 text-amber-600 text-xs font-semibold uppercase tracking-wider mb-2">
              <QrCode className="w-4 h-4" />
              <span>Permanent Table QR</span>
            </div>

            <h3 className="font-bold text-gray-900 text-lg mb-1">{menuData.outlet_name}</h3>
            <p className="text-xs text-gray-500 mb-4">
              Scan with smartphone camera to open digital menu
            </p>

            {/* Permanent QR Code Image */}
            <div className="bg-white p-3 rounded-xl border border-gray-200 inline-block shadow-xs mb-4">
              <img
                src={qrImageUrl}
                alt={`${menuData.outlet_name} QR Code`}
                className="w-48 h-48 mx-auto"
              />
            </div>

            <p className="text-[11px] text-gray-400 mb-4 bg-gray-50 p-2 rounded-lg border border-gray-100">
              🔒 <strong>Permanent & Fixed:</strong> Mount on restaurant tables. Never needs re-printing when menu changes.
            </p>

            <a
              href={qrDownloadUrl}
              download
              style={{ backgroundColor: primaryColor }}
              className="w-full inline-flex items-center justify-center gap-2 py-2.5 text-white text-xs font-semibold rounded-xl transition-all shadow-sm hover:opacity-90"
            >
              <Download className="w-4 h-4" />
              Download Printable PNG
            </a>
          </div>
        </div>
      )}
    </div>
  );
};
