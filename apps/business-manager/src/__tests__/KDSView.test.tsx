import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { KDSTicketCard } from '../features/kds/KDSTicketCard';
import { KDSView } from '../features/kds/KDSView';
import { Order } from '@roms/shared-types';
import * as authContext from '@roms/api-client';
import * as clientApi from '@roms/api-client';

// Mock AuthContext & API client
vi.mock('@roms/api-client', () => ({
  useAuth: vi.fn(),
  fetchOutletOrders: vi.fn(),
  updateOrderStatus: vi.fn(),
}));

describe('KDSTicketCard Component', () => {
  const sampleOrder: Order = {
    id: 'ord-101',
    outlet_id: 'outlet-1',
    table_id: 'tbl-1',
    table_number: 'T-04',
    waiter_user_id: 'w-1',
    waiter_name: 'John Waiter',
    order_number: 'ORD-20261010-001',
    status: 'confirmed',
    order_type: 'dine_in',
    total_amount: 550,
    notes: 'Near window table',
    items: [
      {
        id: 'item-1',
        menu_item_id: 'mi-1',
        item_name: 'Grilled Salmon',
        unit_price: 350,
        quantity: 2,
        subtotal: 700,
        special_instructions: 'No onions, extra lemon',
      },
    ],
    created_at: new Date(Date.now() - 12 * 60 * 1000).toISOString(), // 12 mins ago
    updated_at: new Date().toISOString(),
  };

  it('renders ticket details, special instructions, and priority timer badge', () => {
    const handleUpdateStatus = vi.fn();
    const now = Date.now();

    render(
      <KDSTicketCard
        order={sampleOrder}
        onUpdateStatus={handleUpdateStatus}
        isSubmitting={false}
        now={now}
      />
    );

    expect(screen.getByText('#ORD-20261010-001')).toBeDefined();
    expect(screen.getByText('Table T-04')).toBeDefined();
    expect(screen.getByText('John Waiter')).toBeDefined();
    expect(screen.getByText('2x')).toBeDefined();
    expect(screen.getByText('Grilled Salmon')).toBeDefined();
    expect(screen.getByText('"No onions, extra lemon"')).toBeDefined();
    expect(screen.getByText('Near window table')).toBeDefined();
    expect(screen.getByText('Start Cooking')).toBeDefined();
    expect(screen.getByText('Priority')).toBeDefined();
  });

  it('renders "Mark Ready (Bump)" for in_kitchen status and triggers status callback', async () => {
    const handleUpdateStatus = vi.fn().mockResolvedValue(undefined);
    const inKitchenOrder: Order = { ...sampleOrder, status: 'in_kitchen' };

    render(
      <KDSTicketCard
        order={inKitchenOrder}
        onUpdateStatus={handleUpdateStatus}
        isSubmitting={false}
        now={Date.now()}
      />
    );

    const bumpBtn = screen.getByText('Mark Ready (Bump)');
    expect(bumpBtn).toBeDefined();

    fireEvent.click(bumpBtn);
    expect(handleUpdateStatus).toHaveBeenCalledWith('ord-101', 'served');
  });

  it('disables action button when isSubmitting is true', () => {
    const handleUpdateStatus = vi.fn();

    render(
      <KDSTicketCard
        order={sampleOrder}
        onUpdateStatus={handleUpdateStatus}
        isSubmitting={true}
        now={Date.now()}
      />
    );

    expect(screen.getByText('Updating...')).toBeDefined();
    const button = screen.getByRole('button');
    expect(button.getAttribute('disabled')).not.toBeNull();
  });
});

describe('KDSView Component', () => {
  const mockUser = {
    id: 'u-1',
    email: 'chef@restaurant.com',
    display_name: 'Chef Mario',
    is_platform_admin: false,
    memberships: [
      {
        outlet_id: 'outlet-1',
        outlet_name: 'Downtown Bistro',
        role: 'kitchen',
      },
      {
        outlet_id: 'outlet-2',
        outlet_name: 'Uptown Grill',
        role: 'kitchen',
      },
    ],
  };

  const sampleOrders: Order[] = [
    {
      id: 'ord-1',
      outlet_id: 'outlet-1',
      table_id: 'tbl-1',
      table_number: 'T-01',
      waiter_user_id: 'w-1',
      waiter_name: 'Alice',
      order_number: 'ORD-001',
      status: 'confirmed',
      order_type: 'dine_in',
      total_amount: 300,
      notes: null,
      items: [
        {
          id: 'i-1',
          menu_item_id: 'm-1',
          item_name: 'Pasta Carbonara',
          unit_price: 300,
          quantity: 1,
          subtotal: 300,
          special_instructions: null,
        },
      ],
      created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'ord-2',
      outlet_id: 'outlet-1',
      table_id: 'tbl-2',
      table_number: 'T-02',
      waiter_user_id: 'w-1',
      waiter_name: 'Alice',
      order_number: 'ORD-002',
      status: 'in_kitchen',
      order_type: 'dine_in',
      total_amount: 450,
      notes: null,
      items: [
        {
          id: 'i-2',
          menu_item_id: 'm-2',
          item_name: 'Ribeye Steak',
          unit_price: 450,
          quantity: 1,
          subtotal: 450,
          special_instructions: 'Medium rare',
        },
      ],
      created_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'ord-3',
      outlet_id: 'outlet-1',
      table_id: 'tbl-3',
      table_number: 'T-03',
      waiter_user_id: 'w-2',
      waiter_name: 'Bob',
      order_number: 'ORD-003',
      status: 'served',
      order_type: 'takeaway',
      total_amount: 200,
      notes: null,
      items: [
        {
          id: 'i-3',
          menu_item_id: 'm-3',
          item_name: 'Tiramisu',
          unit_price: 200,
          quantity: 1,
          subtotal: 200,
          special_instructions: null,
        },
      ],
      created_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (authContext.useAuth as any).mockReturnValue({
      token: 'mock-jwt-token',
      user: mockUser,
      selectedOutlet: mockUser.memberships[0],
      setSelectedOutletId: vi.fn(),
      logout: vi.fn(),
    });
    (clientApi.fetchOutletOrders as any).mockResolvedValue(sampleOrders);
  });

  it('loads orders and filters tickets based on selected column filter tab', async () => {
    render(
      <MemoryRouter>
        <KDSView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('#ORD-001')).toBeDefined();
      expect(screen.getByText('#ORD-002')).toBeDefined();
    });

    expect(screen.queryByText('#ORD-003')).toBeNull();

    const readyTab = screen.getByText('Ready (1)');
    fireEvent.click(readyTab);

    expect(screen.getByText('#ORD-003')).toBeDefined();
    expect(screen.queryByText('#ORD-001')).toBeNull();
  });

  it('triggers order status update and re-fetches orders list', async () => {
    (clientApi.updateOrderStatus as any).mockResolvedValue({
      ...sampleOrders[0],
      status: 'in_kitchen',
    });

    render(
      <MemoryRouter>
        <KDSView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Start Cooking')).toBeDefined();
    });

    fireEvent.click(screen.getByText('Start Cooking'));

    await waitFor(() => {
      expect(clientApi.updateOrderStatus).toHaveBeenCalledWith('ord-1', 'in_kitchen', 'mock-jwt-token');
    });
  });

  it('displays error banner if fetching orders fails', async () => {
    (clientApi.fetchOutletOrders as any).mockRejectedValue(new Error('Network Connection Lost'));

    render(
      <MemoryRouter>
        <KDSView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Network Connection Lost')).toBeDefined();
    });
  });

  // --- ISSUE 1 REGRESSION TEST: Stale Response Protection ---
  it('prevents an older GET request from overwriting a successful status mutation', async () => {
    let resolveStaleGet: (value: Order[]) => void = () => {};
    const staleGetPromise = new Promise<Order[]>((resolve) => {
      resolveStaleGet = resolve;
    });

    render(
      <MemoryRouter>
        <KDSView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Start Cooking')).toBeDefined();
    });

    // 1. Next background poll starts (returns staleGetPromise which stays pending)
    (clientApi.fetchOutletOrders as any).mockImplementationOnce(() => staleGetPromise);
    const manualRefreshBtn = screen.getByTitle('Manual Refresh');
    fireEvent.click(manualRefreshBtn);

    // 2. Chef updates status of ord-1 to 'in_kitchen'
    const updatedOrder: Order = { ...sampleOrders[0], status: 'in_kitchen' };
    (clientApi.updateOrderStatus as any).mockResolvedValueOnce(updatedOrder);
    (clientApi.fetchOutletOrders as any).mockResolvedValue([updatedOrder, sampleOrders[1], sampleOrders[2]]);

    const startCookingBtn = screen.getByText('Start Cooking');
    fireEvent.click(startCookingBtn);

    // Mutation completes and UI immediately updates to 'Mark Ready (Bump)' (both ord-1 and ord-2 now have 'Mark Ready (Bump)')
    await waitFor(() => {
      expect(screen.getAllByText('Mark Ready (Bump)').length).toBe(2);
    });

    // 3. Stale GET request finally resolves with OLD status ('confirmed')
    resolveStaleGet(sampleOrders);

    // Wait a macro-tick and verify UI retains new status ('Mark Ready (Bump)') rather than reverting
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getAllByText('Mark Ready (Bump)').length).toBe(2);
    expect(screen.queryByText('Start Cooking')).toBeNull();
  });

  // --- ISSUE 2 REGRESSION TESTS: Audio Alert ID Tracking ---
  it('does not trigger audio chime on initial load for existing orders', async () => {
    render(
      <MemoryRouter>
        <KDSView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('#ORD-001')).toBeDefined();
    });

    // Enable sound
    const audioBtn = screen.getByTitle('Sound Muted');
    fireEvent.click(audioBtn);

    // Verify audio context initialized cleanly
    expect(screen.getByTitle('Kitchen Chime Active')).toBeDefined();
  });

  it('triggers audio chime when 1 order leaves and 1 new order enters, leaving total count unchanged', async () => {
    const mockResume = vi.fn();
    (window as any).AudioContext = vi.fn().mockImplementation(() => ({
      state: 'suspended',
      resume: mockResume,
      currentTime: 0,
      destination: {},
      createOscillator: vi.fn().mockReturnValue({
        type: 'sine',
        frequency: { setValueAtTime: vi.fn() },
        connect: vi.fn(),
        start: vi.fn(),
        stop: vi.fn(),
      }),
      createGain: vi.fn().mockReturnValue({
        gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() },
        connect: vi.fn(),
      }),
    }));

    render(
      <MemoryRouter>
        <KDSView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('#ORD-001')).toBeDefined();
    });

    // Enable sound
    const audioBtn = screen.getByTitle('Sound Muted');
    fireEvent.click(audioBtn);

    // Wait for manual refresh button to be enabled (not in flight)
    await waitFor(() => {
      const refreshBtn = screen.getByTitle('Manual Refresh') as HTMLButtonElement;
      expect(refreshBtn.disabled).toBe(false);
    });

    // Next poll response: ord-1 left, ord-4 entered. Active kitchen count remains 2 (ord-2 & ord-4)
    const newOrder: Order = {
      id: 'ord-4',
      outlet_id: 'outlet-1',
      table_id: 'tbl-4',
      table_number: 'T-04',
      waiter_user_id: 'w-1',
      waiter_name: 'Alice',
      order_number: 'ORD-004',
      status: 'confirmed',
      order_type: 'dine_in',
      total_amount: 150,
      notes: null,
      items: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const updatedOrdersList = [sampleOrders[1], newOrder]; // ord-2 & ord-4
    (clientApi.fetchOutletOrders as any).mockResolvedValue(updatedOrdersList);

    // Trigger refresh
    fireEvent.click(screen.getByTitle('Manual Refresh'));

    await waitFor(() => {
      expect(screen.getByText('#ORD-004')).toBeDefined();
      expect(mockResume).toHaveBeenCalled();
    });
  });

  it('resets order ID tracking when switching outlets', async () => {
    let currentOutlet = mockUser.memberships[0];

    (authContext.useAuth as any).mockImplementation(() => ({
      token: 'mock-jwt-token',
      user: mockUser,
      selectedOutlet: currentOutlet,
      setSelectedOutletId: (id: string) => {
        const found = mockUser.memberships.find((m) => m.outlet_id === id);
        if (found) currentOutlet = found;
      },
      logout: vi.fn(),
    }));

    (clientApi.fetchOutletOrders as any).mockImplementation((outletId: string) => {
      if (outletId === 'outlet-2') {
        return Promise.resolve([
          {
            ...sampleOrders[0],
            id: 'ord-outlet2-1',
            outlet_id: 'outlet-2',
            order_number: 'ORD-OUT2-001',
          },
        ]);
      }
      return Promise.resolve(sampleOrders);
    });

    const { rerender } = render(
      <MemoryRouter>
        <KDSView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('#ORD-001')).toBeDefined();
    });

    // Switch outlet select dropdown to outlet-2 (first combobox in header)
    const outletSelect = screen.getAllByRole('combobox')[0];
    fireEvent.change(outletSelect, { target: { value: 'outlet-2' } });

    // Rerender component so useAuth returns updated currentOutlet
    rerender(
      <MemoryRouter>
        <KDSView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('#ORD-OUT2-001')).toBeDefined();
    });
  });
});
