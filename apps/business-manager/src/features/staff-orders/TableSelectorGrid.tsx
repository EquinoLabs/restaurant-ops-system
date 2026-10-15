import React from 'react';
import { DiningTable } from '@roms/shared-types';

interface TableSelectorGridProps {
  tables: DiningTable[];
  selectedTableId: string | null;
  onSelectTable: (table: DiningTable) => void;
  onAddTable?: () => void;
  isManagerOrOwner: boolean;
}

export const TableSelectorGrid: React.FC<TableSelectorGridProps> = ({
  tables,
  selectedTableId,
  onSelectTable,
  onAddTable,
  isManagerOrOwner,
}) => {
  const getStatusColor = (status: DiningTable['status']) => {
    switch (status) {
      case 'available':
        return 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:border-emerald-500/60';
      case 'occupied':
        return 'bg-amber-500/10 border-amber-500/30 text-amber-400 hover:border-amber-500/60';
      case 'reserved':
        return 'bg-purple-500/10 border-purple-500/30 text-purple-400 hover:border-purple-500/60';
      default:
        return 'bg-slate-800 border-slate-700 text-slate-300';
    }
  };

  const getStatusBadge = (status: DiningTable['status']) => {
    switch (status) {
      case 'available':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Available</span>;
      case 'occupied':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">Occupied</span>;
      case 'reserved':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-400 border border-purple-500/30">Reserved</span>;
    }
  };

  return (
    <div className="bg-slate-900/60 rounded-2xl border border-slate-800 p-6">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-6">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center space-x-2">
            <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <span>Dining Tables Overview</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Select a table to start a new order or view active table service
          </p>
        </div>

        {isManagerOrOwner && onAddTable && (
          <button
            onClick={onAddTable}
            className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-amber-400 border border-slate-700 text-xs font-bold transition-all flex items-center space-x-1"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
            </svg>
            <span>+ Add Table</span>
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {tables.map((table) => {
          const isSelected = selectedTableId === table.id;
          return (
            <button
              key={table.id}
              onClick={() => onSelectTable(table)}
              className={`p-4 rounded-xl border text-left transition-all relative flex flex-col justify-between h-28 ${getStatusColor(
                table.status
              )} ${isSelected ? 'ring-2 ring-amber-400 scale-[1.02]' : ''}`}
            >
              <div className="flex justify-between items-start">
                <span className="text-base font-extrabold text-white tracking-tight">
                  {table.table_number}
                </span>
                {getStatusBadge(table.status)}
              </div>

              <div className="flex justify-between items-end text-xs text-slate-400 font-medium">
                <span>Seats: {table.capacity} guests</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
