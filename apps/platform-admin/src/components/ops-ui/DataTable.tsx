import React from 'react';

export interface DataTableColumn<T> {
  key: string;
  header: string;
  align?: 'left' | 'right';
  width?: string;
  render: (row: T) => React.ReactNode;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  footer?: React.ReactNode;
  minWidth?: string;
  className?: string;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  footer,
  minWidth = '640px',
  className = '',
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
                className="h-10 border-b border-ops-border transition-colors last:border-b-0 hover:bg-ops-canvas"
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={`px-3 text-[13px] leading-[18px] text-ops-text-primary ${
                      col.align === 'right' ? 'text-right tabular-nums' : 'text-left'
                    }`}
                  >
                    {col.render(row)}
                  </td>
                ))}
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
