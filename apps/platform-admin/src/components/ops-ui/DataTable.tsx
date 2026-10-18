import React from 'react';

export interface DataTableColumn<T> {
  key: string;
  header: string;
  align?: 'left' | 'right';
  width?: string;
  /** Whether cell contents represent numeric or date figures requiring tabular numerals */
  tabular?: boolean;
  /** Whether this column represents a primary name requiring single-line truncation (max-w-[240px]) */
  truncateName?: boolean;
  /** Resolves the complete un-truncated string for native HTML title hover inspection */
  getTitle?: (row: T) => string | undefined;
  render: (row: T) => React.ReactNode;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  footer?: React.ReactNode;
  minWidth?: string;
  className?: string;
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  footer,
  minWidth = '640px',
  className = '',
  onRowClick,
}: DataTableProps<T>) {
  return (
    <div className={`flex flex-col overflow-hidden rounded-md border border-ops-border bg-white ${className}`}>
      <div className="w-full overflow-x-auto">
        <table className="w-full table-fixed border-collapse text-left" style={{ minWidth }}>
          <thead>
            <tr className="h-9 border-b border-ops-border bg-ops-canvas">
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  style={col.width ? { width: col.width } : undefined}
                  className={`px-3 text-xs font-semibold leading-4 tracking-wide text-ops-text-secondary ${
                    col.align === 'right' ? 'text-right' : 'text-left'
                  }`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                className={`h-10 border-b border-ops-border transition-colors duration-100 ease-in-out last:border-b-0 ${onRowClick ? 'cursor-pointer hover:bg-ops-canvas' : ''}`}
                onClick={() => onRowClick && onRowClick(row)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onRowClick && onRowClick(row);
                  }
                }}
                tabIndex={onRowClick ? 0 : -1}
                role={onRowClick ? 'button' : undefined}
                aria-label={onRowClick ? 'Row, click to select' : undefined}
              >
                {columns.map((col) => {
                  const isRight = col.align === 'right';
                  const isTabular = col.tabular || isRight;
                  const isNameTruncated = col.truncateName || col.key === 'name' || col.key === 'business' || col.key === 'outlet';
                  const cellTitle = isNameTruncated && col.getTitle ? col.getTitle(row) : undefined;
                  
                  return (
                    <td
                      key={col.key}
                      title={cellTitle}
                      className={`px-3 text-[13px] leading-[18px] text-ops-text-primary ${
                        isRight ? 'text-right' : 'text-left'
                      } ${isTabular ? 'tabular-nums' : ''} ${isNameTruncated ? 'max-w-[240px] truncate' : ''}`}
                    >
                      {col.render(row)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {footer && (
        <div className="flex min-h-10 items-center justify-between border-t border-ops-border bg-white px-4 py-2 text-xs text-ops-text-secondary">
          {footer}
        </div>
      )}
    </div>
  );
}
