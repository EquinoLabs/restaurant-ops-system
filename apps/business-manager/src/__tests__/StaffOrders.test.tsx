import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TableSelectorGrid } from '../features/staff-orders/TableSelectorGrid';
import { OrderEntryPanel } from '../features/staff-orders/OrderEntryPanel';
import { ActiveOrdersQueue } from '../features/staff-orders/ActiveOrdersQueue';
import { DiningTable, Order } from '@roms/shared-types';
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

describe('ActiveOrdersQueue Component - Bill Settlement Workflow', () => {
  const sampleOrders: Order[] = [
    {
      id: 'order-1',
      outlet_id: 'outlet-1',
      table_id: 'table-1',
      table_number: 'T-01',
      order_number: 'ORD-101',
      status: 'served',
      payment_status: 'unpaid',
      subtotal: 500,
      tax_amount: 25,
      total_amount: 525,
      notes: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      items: [
        {
          id: 'item-1',
          order_id: 'order-1',
          menu_item_id: 'item-1',
          item_name: 'Trout Fry',
          item_price: 500,
          quantity: 1,
          item_notes: null,
        },
      ],
    },
    {
      id: 'order-2',
      outlet_id: 'outlet-1',
      table_id: 'table-2',
      table_number: 'T-02',
      order_number: 'ORD-102',
      status: 'served',
      payment_status: 'paid',
      payment_method: 'upi',
      settled_at: new Date().toISOString(),
      settled_by_user_id: 'user-mgr',
      settled_by_name: 'Manager Bob',
      subtotal: 300,
      tax_amount: 15,
      total_amount: 315,
      notes: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      items: [
        {
          id: 'item-2',
          order_id: 'order-2',
          menu_item_id: 'item-2',
          item_name: 'Coffee',
          item_price: 300,
          quantity: 1,
          item_notes: null,
        },
      ],
    },
  ];

  it('renders payment status badges and restricts completion for unpaid served orders', () => {
    const handleUpdateStatus = vi.fn().mockResolvedValue(undefined);
    const handleSettleOrder = vi.fn().mockResolvedValue(undefined);

    render(
      <ActiveOrdersQueue
        orders={sampleOrders}
        onUpdateStatus={handleUpdateStatus}
        onSettleOrder={handleSettleOrder}
        loading={false}
      />
    );

    // Badges
    const unpaidBadge = screen.getByTestId('payment-badge-order-1');
    expect(unpaidBadge.textContent).toContain('Unpaid');

    const paidBadge = screen.getByTestId('payment-badge-order-2');
    expect(paidBadge.textContent).toContain('Paid (UPI)');

    // For unpaid order-1 (served): table completion button is NOT available
    expect(screen.queryByTestId('complete-btn-order-1')).toBeNull();
    // But Settle Bill button IS available
    expect(screen.getByTestId('settle-btn-order-1')).toBeDefined();

    // For paid order-2 (served): table completion button IS available
    expect(screen.getByTestId('complete-btn-order-2')).toBeDefined();
    // Paid order does NOT have Settle Bill button
    expect(screen.queryByTestId('settle-btn-order-2')).toBeNull();
  });

  it('opens settlement modal, requires explicit confirmation, and settles with chosen method', async () => {
    const handleUpdateStatus = vi.fn().mockResolvedValue(undefined);
    const handleSettleOrder = vi.fn().mockResolvedValue(undefined);

    render(
      <ActiveOrdersQueue
        orders={sampleOrders}
        onUpdateStatus={handleUpdateStatus}
        onSettleOrder={handleSettleOrder}
        loading={false}
      />
    );

    // Click Settle Bill on order-1
    fireEvent.click(screen.getByTestId('settle-btn-order-1'));

    // Modal is opened
    expect(screen.getByText('Settle Order Bill')).toBeDefined();
    expect(screen.getByTestId('settle-modal-amount').textContent).toContain('₹525.00');

    // Confirm button should be disabled initially (checkbox not checked)
    const submitBtn = screen.getByTestId('settle-confirm-submit-btn') as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(true);

    // Switch payment method to UPI
    fireEvent.click(screen.getByTestId('method-upi-btn'));

    // Check confirmation checkbox
    const checkbox = screen.getByTestId('settle-confirm-checkbox');
    fireEvent.click(checkbox);
    expect(submitBtn.disabled).toBe(false);

    // Submit settlement
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(handleSettleOrder).toHaveBeenCalledWith('order-1', 'upi');
    });
  });

  it('displays error banner if onSettleOrder fails', async () => {
    const handleUpdateStatus = vi.fn().mockResolvedValue(undefined);
    const handleSettleOrder = vi.fn().mockRejectedValue(new Error('Payment conflict: already settled'));

    render(
      <ActiveOrdersQueue
        orders={sampleOrders}
        onUpdateStatus={handleUpdateStatus}
        onSettleOrder={handleSettleOrder}
        loading={false}
      />
    );

    fireEvent.click(screen.getByTestId('settle-btn-order-1'));
    fireEvent.click(screen.getByTestId('settle-confirm-checkbox'));
    fireEvent.click(screen.getByTestId('settle-confirm-submit-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('settle-error-banner').textContent).toContain('Payment conflict: already settled');
    });
  });

  it('allows completing and freeing table for paid served orders', () => {
    const handleUpdateStatus = vi.fn().mockResolvedValue(undefined);
    const handleSettleOrder = vi.fn().mockResolvedValue(undefined);

    render(
      <ActiveOrdersQueue
        orders={sampleOrders}
        onUpdateStatus={handleUpdateStatus}
        onSettleOrder={handleSettleOrder}
        loading={false}
      />
    );

    const completeBtn = screen.getByTestId('complete-btn-order-2');
    fireEvent.click(completeBtn);

    expect(handleUpdateStatus).toHaveBeenCalledWith('order-2', 'completed');
  });
});
