import React, { useState, useEffect } from 'react';
import { DiningTable, TableUpdatePayload } from '@roms/shared-types';

interface TableEditorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (payload: TableUpdatePayload) => Promise<void>;
  table?: DiningTable | null;
}

const STATUSES: Array<DiningTable['status']> = ['available', 'occupied', 'reserved'];

export const TableEditorModal: React.FC<TableEditorModalProps> = ({
  isOpen,
  onClose,
  onSave,
  table,
}) => {
  const [tableNumber, setTableNumber] = useState('');
  const [capacity, setCapacity] = useState(4);
  const [status, setStatus] = useState<DiningTable['status']>('available');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (table) {
      setTableNumber(table.table_number);
      setCapacity(table.capacity);
      setStatus(table.status);
    } else {
      setTableNumber('');
      setCapacity(4);
      setStatus('available');
    }
    setError(null);
  }, [table, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!tableNumber.trim()) {
      setError('Table number is required.');
      return;
    }
    if (!Number.isInteger(Number(capacity)) || Number(capacity) < 1) {
      setError('Capacity must be a whole number of at least 1.');
      return;
    }
    try {
      setIsSubmitting(true);
      if (table) {
        await onSave({
          table_number: tableNumber.trim(),
          capacity: Number(capacity),
          status,
        });
      } else {
        await onSave({
          table_number: tableNumber.trim(),
          capacity: Number(capacity),
        });
      }
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to save table.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl max-w-md w-full p-6 shadow-2xl text-slate-100">
        <div className="flex justify-between items-center pb-4 border-b border-slate-800">
          <h3 className="text-lg font-bold text-white">
            {table ? 'Edit Table' : 'Create New Table'}
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-slate-800"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
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
            <label
              htmlFor="table-number-input"
              className="block text-xs font-semibold uppercase tracking-wider text-slate-300"
            >
              Table Number *
            </label>
            <input
              id="table-number-input"
              type="text"
              required
              value={tableNumber}
              onChange={(e) => setTableNumber(e.target.value)}
              placeholder="e.g. T-01"
              className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>

          <div>
            <label
              htmlFor="table-capacity-input"
              className="block text-xs font-semibold uppercase tracking-wider text-slate-300"
            >
              Seat Capacity *
            </label>
            <input
              id="table-capacity-input"
              type="number"
              min={1}
              required
              value={capacity}
              onChange={(e) => setCapacity(Number(e.target.value))}
              className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/50"
            />
          </div>

          {table && (
            <div>
              <label
                htmlFor="table-status-input"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-300"
              >
                Status
              </label>
              <select
                id="table-status-input"
                value={status}
                onChange={(e) => setStatus(e.target.value as DiningTable['status'])}
                className="mt-1 w-full px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 text-white text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/50 cursor-pointer"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          )}

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
              {isSubmitting ? 'Saving...' : table ? 'Save Changes' : 'Create Table'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
