import React, { useState, useEffect } from 'react';
import { AdminMenuItem, AdminMenuCategory, ItemPayload } from '../../types/adminMenu';

interface ItemEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (payload: ItemPayload) => Promise<void>;
  categories: AdminMenuCategory[];
  item?: AdminMenuItem | null;
  defaultCategoryId?: string;
  currency?: string;
  onUploadImage?: (file: File) => Promise<void>;
  onDeleteImage?: () => Promise<void>;
}

export const ItemEditorModal: React.FC<ItemEditorModalProps> = ({
  isOpen,
  onClose,
  onSave,
  categories,
  item,
  defaultCategoryId,
  currency = 'INR',
  onUploadImage,
  onDeleteImage,
}) => {
  const [categoryId, setCategoryId] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [price, setPrice] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [isAvailable, setIsAvailable] = useState(true);
  const [isActive, setIsActive] = useState(true);
  const [sortOrder, setSortOrder] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (item) {
      setCategoryId(item.category_id);
      setName(item.name);
      setDescription(item.description || '');
      setPrice(String(item.price));
      setImageUrl(item.image_url || '');
      setIsAvailable(item.is_available);
      setIsActive(item.is_active);
      setSortOrder(item.sort_order);
    } else {
      setCategoryId(defaultCategoryId || (categories[0]?.id || ''));
      setName('');
      setDescription('');
      setPrice('');
      setImageUrl('');
      setIsAvailable(true);
      setIsActive(true);
      setSortOrder(0);
    }
    setError(null);
  }, [item, defaultCategoryId, categories, isOpen]);

  if (!isOpen) return null;

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      setError('Selected image exceeds maximum allowed size of 5MB.');
      return;
    }

    if (onUploadImage) {
      try {
        setIsUploadingImage(true);
        setError(null);
        await onUploadImage(file);
      } catch (err: any) {
        setError(err.message || 'Failed to upload image to Cloudflare R2.');
      } finally {
        setIsUploadingImage(false);
      }
    }
  };

  const handleRemoveImage = async () => {
    if (onDeleteImage) {
      try {
        setIsUploadingImage(true);
        setError(null);
        await onDeleteImage();
        setImageUrl('');
      } catch (err: any) {
        setError(err.message || 'Failed to delete image.');
      } finally {
        setIsUploadingImage(false);
      }
    } else {
      setImageUrl('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError('Item name is required.');
      return;
    }
    if (!categoryId) {
      setError('Please select a category.');
      return;
    }
    if (!price || isNaN(Number(price)) || Number(price) < 0) {
      setError('Please enter a valid non-negative price.');
      return;
    }

    try {
      setIsSubmitting(true);
      await onSave({
        category_id: categoryId,
        name: name.trim(),
        description: description.trim() || null,
        price: Number(price),
        image_url: imageUrl.trim() || null,
        is_available: isAvailable,
        is_active: isActive,
        sort_order: Number(sortOrder),
      });
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save menu item.');
    } finally {
      setIsSubmitting(false);
    }
  };


  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-lg w-full p-6 shadow-2xl text-slate-100 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center pb-4 border-b border-slate-800">
          <h3 className="text-lg font-bold text-white">
            {item ? 'Edit Menu Item' : 'Add New Menu Item'}
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-slate-800"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Category *
            </label>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            >
              {categories.map((cat) => (
                <option key={cat.id} value={cat.id}>
                  {cat.name} {!cat.is_active ? '(Archived)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Item Name *
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Trout Fish Fry"
              className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Price ({currency}) *
              </label>
              <input
                type="number"
                step="0.01"
                required
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="450.00"
                className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Display Order
              </label>
              <input
                type="number"
                value={sortOrder}
                onChange={(e) => setSortOrder(Number(e.target.value))}
                className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/50"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
              Description (Optional)
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Delicious description for customers..."
              className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
              Food Item Image (Cloudflare R2)
            </label>
            {imageUrl ? (
              <div className="flex items-center space-x-4 p-3 bg-slate-800/80 border border-slate-700 rounded-xl">
                <img
                  src={imageUrl}
                  alt="Item Preview"
                  className="w-16 h-16 object-cover rounded-lg border border-slate-700 shadow-sm"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-emerald-400 truncate">Image Connected</p>
                  <p className="text-[10px] text-slate-400 truncate">{imageUrl}</p>
                  <div className="mt-2 flex items-center space-x-2">
                    <label className="cursor-pointer text-[11px] font-semibold text-amber-400 hover:text-amber-300">
                      {isUploadingImage ? 'Uploading...' : 'Replace'}
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        onChange={handleFileChange}
                        disabled={isUploadingImage}
                        className="hidden"
                      />
                    </label>
                    <span className="text-slate-600">•</span>
                    <button
                      type="button"
                      onClick={handleRemoveImage}
                      disabled={isUploadingImage}
                      className="text-[11px] font-semibold text-red-400 hover:text-red-300 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <label className="flex flex-col items-center justify-center p-4 border-2 border-dashed border-slate-700 hover:border-amber-500/50 rounded-xl bg-slate-800/40 hover:bg-slate-800/80 cursor-pointer transition-all">
                  <svg className="w-6 h-6 text-slate-400 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  <span className="text-xs font-semibold text-slate-300">
                    {isUploadingImage ? 'Uploading file...' : 'Upload image (JPEG, PNG, WebP)'}
                  </span>
                  <span className="text-[10px] text-slate-500">Max file size 5MB</span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleFileChange}
                    disabled={isUploadingImage}
                    className="hidden"
                  />
                </label>

                <div className="relative flex items-center justify-center">
                  <div className="border-t border-slate-800 w-full"></div>
                  <span className="bg-slate-900 px-2 text-[10px] text-slate-500 uppercase font-bold absolute">or URL</span>
                </div>

                <input
                  type="url"
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  placeholder="https://images.unsplash.com/..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white placeholder-slate-500 text-xs focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                />
              </div>
            )}
          </div>


          <div className="grid grid-cols-2 gap-4 pt-2">
            <div className="flex items-center">
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={isAvailable}
                  onChange={(e) => setIsAvailable(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-500"></div>
                <span className="ml-3 text-xs font-medium text-slate-300">
                  {isAvailable ? 'In Stock' : 'Out of Stock'}
                </span>
              </label>
            </div>

            <div className="flex items-center">
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500"></div>
                <span className="ml-3 text-xs font-medium text-slate-300">
                  {isActive ? 'Active' : 'Archived'}
                </span>
              </label>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800 text-xs font-semibold transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-all disabled:opacity-50"
            >
              {isSubmitting ? 'Saving...' : item ? 'Save Changes' : 'Create Item'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
