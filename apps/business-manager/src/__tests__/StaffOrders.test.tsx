import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TableSelectorGrid } from '../features/staff-orders/TableSelectorGrid';
import { OrderEntryPanel } from '../features/staff-orders/OrderEntryPanel';
import { DiningTable } from '@roms/shared-types';
import { AdminMenuCategory } from '@roms/shared-types';

describe('TableSelectorGrid Component', () => {
  const sampleTables: DiningTable[] = [
    {
      id: 'table-1',
      outlet_id: 'outlet-1',
      table_number: 'T-01',
      capacity: 4,
      status: 'available',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'table-2',
      outlet_id: 'outlet-1',
      table_number: 'T-02',
      capacity: 2,
      status: 'occupied',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  it('renders tables list with status badges and triggers select callback', () => {
    const handleSelect = vi.fn();
    render(
      <TableSelectorGrid
        tables={sampleTables}
        selectedTableId={null}
        onSelectTable={handleSelect}
        isManagerOrOwner={true}
      />
    );

    expect(screen.getByText('T-01')).toBeDefined();
    expect(screen.getByText('T-02')).toBeDefined();
    expect(screen.getByText('Available')).toBeDefined();
    expect(screen.getByText('Occupied')).toBeDefined();

    fireEvent.click(screen.getByText('T-01'));
    expect(handleSelect).toHaveBeenCalledWith(sampleTables[0]);
  });
});

describe('OrderEntryPanel Component', () => {
  const sampleCategories: AdminMenuCategory[] = [
    {
      id: 'cat-1',
      outlet_id: 'outlet-1',
      name: 'Starters',
      description: 'Snacks',
      sort_order: 1,
      is_active: true,
      items: [
        {
          id: 'item-1',
          outlet_id: 'outlet-1',
          category_id: 'cat-1',
          name: 'Trout Fry',
          description: 'Crispy fish',
          price: 450,
          image_url: null,
          is_available: true,
          is_active: true,
          sort_order: 1,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  it('allows tapping menu item to add to ticket and calculates total', () => {
    const handleSubmitted = vi.fn().mockResolvedValue(undefined);

    render(
      <OrderEntryPanel
        selectedTable={null}
        categories={sampleCategories}
        onOrderSubmitted={handleSubmitted}
      />
    );

    expect(screen.getByText('Trout Fry')).toBeDefined();
    fireEvent.click(screen.getByText('Trout Fry'));

    expect(screen.getAllByText('₹450.00').length).toBeGreaterThan(0);
  });
});
