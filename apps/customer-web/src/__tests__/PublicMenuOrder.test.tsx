import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { PublicMenuView } from '../features/public-menu/PublicMenuView';
import { OutletPublicMenu } from '@roms/shared-types';
import { Order } from '@roms/shared-types';
import * as clientApi from '@roms/api-client';

// Mock API client
vi.mock('@roms/api-client', () => ({
  fetchPublicMenu: vi.fn(),
  submitPublicOrder: vi.fn(),
}));

describe('Customer QR Self-Ordering Mobile Cart & Checkout UI (Task G.3)', () => {
  const mockMenu: OutletPublicMenu = {
    outlet_id: 'outlet-123',
    outlet_name: 'The Himalayan Den',
    public_slug: 'himalayan-den',
    timezone: 'Asia/Kolkata',
    address: 'Mall Road, Manali',
    primary_color: '#d97706',
    cover_image_url: null,
    logo_url: null,
    currency: 'INR',
    categories: [
      {
        id: 'cat-1',
        name: 'Mains',
        description: 'Traditional signatures',
        sort_order: 1,
        items: [
          {
            id: 'item-101',
            name: 'Himachali Trout Fry',
            description: 'Fresh trout pan-seared with herbs',
            price: 450,
            image_url: null,
            is_available: true,
            sort_order: 1,
          },
          {
            id: 'item-102',
            name: 'Siddu with Ghee',
            description: 'Steamed wheat bun with walnut stuffing',
            price: 220,
            image_url: null,
            is_available: true,
            sort_order: 2,
          },
          {
            id: 'item-103',
            name: 'Seasonal Apple Tart',
            description: 'Fresh local orchard apples',
            price: 180,
            image_url: null,
            is_available: false, // Sold out item
            sort_order: 3,
          },
        ],
      },
    ],
  };

  const mockCreatedOrder: Order = {
    id: 'ord-999',
    outlet_id: 'outlet-123',
    table_id: 'tbl-5',
    table_number: 'T-05',
    waiter_user_id: null,
    waiter_name: null,
    order_number: 'ORD-20261013-088',
    status: 'pending',
    order_type: 'dine_in',
    total_amount: 670,
    notes: 'Please bring water with order',
    items: [
      {
        id: 'ord-item-1',
        menu_item_id: 'item-101',
        item_name: 'Himachali Trout Fry',
        unit_price: 450,
        quantity: 1,
        subtotal: 450,
        special_instructions: 'Extra crisp',
      },
      {
        id: 'ord-item-2',
        menu_item_id: 'item-102',
        item_name: 'Siddu with Ghee',
        unit_price: 220,
        quantity: 1,
        subtotal: 220,
        special_instructions: null,
      },
    ],
    created_at: '2026-10-13T10:00:00Z',
    updated_at: '2026-10-13T10:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(clientApi.fetchPublicMenu).mockResolvedValue(mockMenu);
  });

  const renderWithRoute = (initialPath = '/m/himalayan-den?table=T-05') => {
    return render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/m/:publicSlug" element={<PublicMenuView />} />
        </Routes>
      </MemoryRouter>
    );
  };

  it('detects table query parameter from URL and displays Table badge', async () => {
    renderWithRoute('/m/himalayan-den?table=T-05');

    await waitFor(() => {
      expect(screen.getByText('The Himalayan Den')).toBeDefined();
    });

    const tableBadge = screen.getByTestId('header-table-badge');
    expect(tableBadge).toBeDefined();
    expect(tableBadge.textContent).toContain('Table T-05');
  });

  it('defaults to Takeaway badge when table query parameter is missing', async () => {
    renderWithRoute('/m/himalayan-den');

    await waitFor(() => {
      expect(screen.getByText('The Himalayan Den')).toBeDefined();
    });

    const takeawayBadge = screen.getByTestId('header-takeaway-badge');
    expect(takeawayBadge).toBeDefined();
    expect(takeawayBadge.textContent).toContain('Takeaway');
  });

  it('shows Sold Out for unavailable items and disables cart actions', async () => {
    renderWithRoute('/m/himalayan-den?table=T-05');

    await waitFor(() => {
      expect(screen.getByText('Seasonal Apple Tart')).toBeDefined();
    });

    expect(screen.getByText('Sold Out')).toBeDefined();
    expect(screen.queryByLabelText('Add Seasonal Apple Tart to cart')).toBeNull();
  });

  it('adds items to cart, updates quantity, and displays sticky bottom bar', async () => {
    renderWithRoute('/m/himalayan-den?table=T-05');

    await waitFor(() => {
      expect(screen.getByText('Himachali Trout Fry')).toBeDefined();
    });

    // Cart bar should not be present initially
    expect(screen.queryByTestId('cart-badge-count')).toBeNull();

    // Click "+ Add" on first item
    const addTroutBtn = screen.getByLabelText('Add Himachali Trout Fry to cart');
    fireEvent.click(addTroutBtn);

    // Quantity stepper should appear on item card
    expect(screen.getByLabelText('Himachali Trout Fry quantity').textContent).toBe('1');

    // Sticky bottom bar should appear with 1 item, ₹450.00
    expect(screen.getByTestId('cart-badge-count').textContent).toBe('1');
    expect(screen.getByTestId('cart-bar-total').textContent).toContain('₹450.00');

    // Click "+" to increment quantity to 2
    const incTroutBtn = screen.getByLabelText('Increase Himachali Trout Fry quantity');
    fireEvent.click(incTroutBtn);

    expect(screen.getByLabelText('Himachali Trout Fry quantity').textContent).toBe('2');
    expect(screen.getByTestId('cart-badge-count').textContent).toBe('2');
    expect(screen.getByTestId('cart-bar-total').textContent).toContain('₹900.00');

    // Click "-" to decrement quantity back to 1
    const decTroutBtn = screen.getByLabelText('Decrease Himachali Trout Fry quantity');
    fireEvent.click(decTroutBtn);

    expect(screen.getByLabelText('Himachali Trout Fry quantity').textContent).toBe('1');
    expect(screen.getByTestId('cart-badge-count').textContent).toBe('1');
    expect(screen.getByTestId('cart-bar-total').textContent).toContain('₹450.00');

    // Click "-" again to remove item completely
    fireEvent.click(decTroutBtn);

    // Cart bar disappears
    expect(screen.queryByTestId('cart-badge-count')).toBeNull();
    expect(screen.getByLabelText('Add Himachali Trout Fry to cart')).toBeDefined();
  });

  it('opens cart drawer, edits notes/instructions, and displays table context', async () => {
    renderWithRoute('/m/himalayan-den?table=T-05');

    await waitFor(() => {
      expect(screen.getByText('Himachali Trout Fry')).toBeDefined();
    });

    // Add Trout Fry and Siddu
    fireEvent.click(screen.getByLabelText('Add Himachali Trout Fry to cart'));
    fireEvent.click(screen.getByLabelText('Add Siddu with Ghee to cart'));

    expect(screen.getByTestId('cart-badge-count').textContent).toBe('2');

    // Open Cart Drawer
    fireEvent.click(screen.getByText('View Cart'));

    // Cart Drawer is open
    expect(screen.getByRole('dialog', { name: 'Your Order Cart' })).toBeDefined();
    expect(screen.getByTestId('cart-table-badge').textContent).toContain('Table T-05');
    expect(screen.getByTestId('cart-modal-total').textContent).toContain('₹670.00');

    // Add special note for Trout Fry
    const addNoteBtn = screen.getAllByText('+ Add special note')[0];
    fireEvent.click(addNoteBtn);

    const noteInput = screen.getByLabelText('Special instructions for Himachali Trout Fry');
    fireEvent.change(noteInput, { target: { value: 'Extra crisp' } });
    expect((noteInput as HTMLInputElement).value).toBe('Extra crisp');

    // Add general order note
    const orderNotesArea = screen.getByLabelText('Special Requests for Outlet (Optional)');
    fireEvent.change(orderNotesArea, { target: { value: 'Please bring water with order' } });
    expect((orderNotesArea as HTMLTextAreaElement).value).toBe('Please bring water with order');

    // Close drawer
    fireEvent.click(screen.getByLabelText('Close cart drawer'));
    expect(screen.queryByRole('dialog', { name: 'Your Order Cart' })).toBeNull();
  });

  it('submits order with idempotency key, clears cart, and displays confirmation modal', async () => {
    vi.mocked(clientApi.submitPublicOrder).mockResolvedValue(mockCreatedOrder);

    renderWithRoute('/m/himalayan-den?table=T-05');

    await waitFor(() => {
      expect(screen.getByText('Himachali Trout Fry')).toBeDefined();
    });

    fireEvent.click(screen.getByLabelText('Add Himachali Trout Fry to cart'));
    fireEvent.click(screen.getByLabelText('Add Siddu with Ghee to cart'));

    // Open cart
    fireEvent.click(screen.getByText('View Cart'));

    // Set special note
    fireEvent.click(screen.getAllByText('+ Add special note')[0]);
    fireEvent.change(screen.getByLabelText('Special instructions for Himachali Trout Fry'), {
      target: { value: 'Extra crisp' },
    });

    // Set general note
    fireEvent.change(screen.getByLabelText('Special Requests for Outlet (Optional)'), {
      target: { value: 'Please bring water with order' },
    });

    // Click Place Order
    const placeOrderBtn = screen.getByTestId('place-order-button');
    fireEvent.click(placeOrderBtn);

    await waitFor(() => {
      expect(clientApi.submitPublicOrder).toHaveBeenCalledTimes(1);
    });

    const [slug, payload, idempKey] = vi.mocked(clientApi.submitPublicOrder).mock.calls[0];
    expect(slug).toBe('himalayan-den');
    expect(payload.table_number).toBe('T-05');
    expect(payload.order_type).toBe('dine_in');
    expect(payload.notes).toBe('Please bring water with order');
    expect(payload.items).toHaveLength(2);
    expect(payload.items[0]).toEqual({
      menu_item_id: 'item-101',
      quantity: 1,
      special_instructions: 'Extra crisp',
    });
    expect(idempKey).toBeTruthy();
    expect(payload.idempotency_key).toBe(idempKey);

    // Verify Order Confirmation Modal
    await waitFor(() => {
      expect(screen.getByText('Order Placed!')).toBeDefined();
    });

    expect(screen.getByTestId('confirmed-order-number').textContent).toBe('ORD-20261013-088');
    expect(screen.getByTestId('confirmed-status-badge').textContent).toContain('Awaiting Staff Confirmation');
    expect(screen.getByTestId('confirmed-table-badge').textContent).toContain('Table T-05');
    expect(screen.getByTestId('confirmed-order-total').textContent).toContain('₹670.00');

    // Cart bottom bar is cleared
    expect(screen.queryByTestId('cart-badge-count')).toBeNull();

    // Click "Order More / Back to Menu" closes confirmation
    fireEvent.click(screen.getByTestId('confirmation-back-to-menu'));
    expect(screen.queryByText('Order Placed!')).toBeNull();
  });

  it('retains customer cart and displays error banner on API failure, allowing retry with same key', async () => {
    vi.mocked(clientApi.submitPublicOrder)
      .mockRejectedValueOnce(new Error("Table 'T-05' was not found in this outlet."))
      .mockResolvedValueOnce(mockCreatedOrder);

    renderWithRoute('/m/himalayan-den?table=T-05');

    await waitFor(() => {
      expect(screen.getByText('Himachali Trout Fry')).toBeDefined();
    });

    fireEvent.click(screen.getByLabelText('Add Himachali Trout Fry to cart'));
    fireEvent.click(screen.getByText('View Cart'));

    // First attempt fails
    fireEvent.click(screen.getByTestId('place-order-button'));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeDefined();
    });

    expect(screen.getByText("Table 'T-05' was not found in this outlet.")).toBeDefined();
    expect(screen.getByText('Your cart items have been saved. You can try again now.')).toBeDefined();

    // Items remain intact in cart
    expect(screen.getAllByText('Himachali Trout Fry').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId('cart-modal-total').textContent).toContain('₹450.00');


    const firstKey = vi.mocked(clientApi.submitPublicOrder).mock.calls[0][2];

    // Retry placing order without modifying cart
    fireEvent.click(screen.getByTestId('place-order-button'));

    await waitFor(() => {
      expect(clientApi.submitPublicOrder).toHaveBeenCalledTimes(2);
    });

    const secondKey = vi.mocked(clientApi.submitPublicOrder).mock.calls[1][2];
    // Must REUSE the same idempotency key for retry!
    expect(secondKey).toBe(firstKey);

    // Successfully opens confirmation
    await waitFor(() => {
      expect(screen.getByText('Order Placed!')).toBeDefined();
    });
  });
});
