import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { fetchPublicMenu } from '../../api/client';
import { OutletPublicMenu } from '../../types/menu';
import { CategorySection } from './CategorySection';
import { MenuSkeleton } from './MenuSkeleton';
import { NotFoundView } from './NotFoundView';
import { Error500View } from './Error500View';
import { Search, MapPin, Sparkles, QrCode, Download, X } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export const PublicMenuView: React.FC = () => {
  const { publicSlug } = useParams<{ publicSlug: string }>();
  const [menuData, setMenuData] = useState<OutletPublicMenu | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeCategoryId, setActiveCategoryId] = useState<string | null>(null);
  const [showQrModal, setShowQrModal] = useState<boolean>(false);

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

  return (
    <div className="max-w-md mx-auto min-h-screen bg-gray-50 pb-12 antialiased relative">
      {/* Outlet Header */}
      <header className="bg-white border-b border-gray-100 p-5 sticky top-0 z-20 shadow-xs">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2 text-amber-600 text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Digital Menu</span>
          </div>

          <button
            onClick={() => setShowQrModal(true)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-amber-50 hover:bg-amber-100 text-amber-800 text-xs font-medium rounded-lg border border-amber-200/80 transition-all"
            title="View permanent table QR code"
          >
            <QrCode className="w-3.5 h-3.5 text-amber-600" />
            <span>QR Stand</span>
          </button>
        </div>

        <h1 className="text-xl font-extrabold text-gray-900 tracking-tight">
          {menuData.outlet_name}
        </h1>
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
          {menuData.categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => scrollToCategory(cat.id)}
              className={`px-3.5 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all ${
                activeCategoryId === cat.id
                  ? 'bg-amber-600 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200/70'
              }`}
            >
              {cat.name}
            </button>
          ))}
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
            />
          ))
        )}
      </main>

      {/* Footer Branding */}
      <footer className="text-center py-6 border-t border-gray-200/60 text-xs text-gray-400">
        Powered by <span className="font-semibold text-gray-600">ROMS Digital Menu</span>
      </footer>

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
              className="w-full inline-flex items-center justify-center gap-2 py-2.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-xl transition-all shadow-sm"
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
