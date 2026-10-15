import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { TableEditorModal } from '../features/tables/TableEditorModal';
import { TablesManagerView } from '../features/tables/TablesManagerView';
import { DiningTable, UserMe } from '@roms/shared-types';

const mockFetchOutletTables = vi.fn();
const mockCreateTable = vi.fn();
const mockUpdateTable = vi.fn();

let mockAuthState: any;

vi.mock('@roms/api-client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@roms/api-client')>();
  return {
    ...original,
    fetchOutletTables: (...args: any[]) => mockFetchOutletTables(...args),
    createTable: (...args: any[]) => mockCreateTable(...args),
    updateTable: (...args: any[]) => mockUpdateTable(...args),
    useAuth: () => mockAuthState,
  };
});

const makeTable = (overrides: Partial<DiningTable> = {}): DiningTable => ({
  id: 'table-1',
  outlet_id: 'outlet-1',
  table_number: 'T-01',
  capacity: 4,
  status: 'available',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

const makeUser = (role: string): UserMe => ({
  id: 'user-1',
  email: 'manager@example.com',
  display_name: 'Manager User',
  status: 'active',
  is_platform_admin: false,
  memberships: [
    {
      business_id: 'biz-1',
      business_name: 'Himachal Hospitality',
      outlet_id: 'outlet-1',
      outlet_name: 'Shimla Main',
      public_slug: 'shimla-main',
      role,
    },
  ],
});

describe('TableEditorModal Component', () => {
  it('renders create form and calls onSave with trimmed payload on submit', async () => {
    const handleSave = vi.fn().mockResolvedValue(undefined);
    const handleClose = vi.fn();

    render(
      <TableEditorModal isOpen={true} onClose={handleClose} onSave={handleSave} table={null} />
    );

    expect(screen.getByText('Create New Table')).toBeDefined();

    fireEvent.change(screen.getByPlaceholderText('e.g. T-01'), {
      target: { value: 'T-09' },
    });
    fireEvent.change(screen.getByLabelText(/Seat Capacity/), {
      target: { value: '6' },
    });

    fireEvent.click(screen.getByText('Create Table'));

    await waitFor(() => {
      expect(handleSave).toHaveBeenCalledWith({
        table_number: 'T-09',
        capacity: 6,
      });
    });
    expect(handleClose).toHaveBeenCalled();
  });

  it('renders edit form with status field and calls onSave with full payload', async () => {
    const handleSave = vi.fn().mockResolvedValue(undefined);
    const handleClose = vi.fn();
    const table = makeTable({ table_number: 'T-05', capacity: 2, status: 'occupied' });

    render(
      <TableEditorModal isOpen={true} onClose={handleClose} onSave={handleSave} table={table} />
    );

    expect(screen.getByText('Edit Table')).toBeDefined();
    expect(screen.getByDisplayValue('T-05')).toBeDefined();

    fireEvent.change(screen.getByLabelText(/Seat Capacity/), {
      target: { value: '3' },
    });

    fireEvent.change(screen.getByLabelText(/Status/), {
      target: { value: 'reserved' },
    });

    fireEvent.click(screen.getByText('Save Changes'));

    await waitFor(() => {
      expect(handleSave).toHaveBeenCalledWith({
        table_number: 'T-05',
        capacity: 3,
        status: 'reserved',
      });
    });
  });

  it('shows validation error for empty table number', async () => {
    const handleSave = vi.fn();
    const handleClose = vi.fn();

    render(
      <TableEditorModal isOpen={true} onClose={handleClose} onSave={handleSave} table={null} />
    );

    fireEvent.submit(screen.getByText('Create Table').closest('form')!);

    expect(screen.getByText('Table number is required.')).toBeDefined();
    expect(handleSave).not.toHaveBeenCalled();
  });

  it('shows server error message when onSave rejects', async () => {
    const handleSave = vi.fn().mockRejectedValue(new Error('Table already exists'));
    const handleClose = vi.fn();

    render(
      <TableEditorModal isOpen={true} onClose={handleClose} onSave={handleSave} table={null} />
    );

    fireEvent.change(screen.getByPlaceholderText('e.g. T-01'), {
      target: { value: 'T-01' },
    });
    fireEvent.click(screen.getByText('Create Table'));

    await waitFor(() => {
      expect(screen.getByText('Table already exists')).toBeDefined();
    });
    expect(handleClose).not.toHaveBeenCalled();
  });
});

describe('TablesManagerView Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads and renders tables for the selected outlet', async () => {
    mockAuthState = {
      token: 'token-123',
      user: makeUser('owner'),
      selectedOutlet: {
        business_id: 'biz-1',
        business_name: 'Himachal Hospitality',
        outlet_id: 'outlet-1',
        outlet_name: 'Shimla Main',
        public_slug: 'shimla-main',
        role: 'owner',
      },
      setSelectedOutletId: vi.fn(),
      logout: vi.fn(),
    };
    mockFetchOutletTables.mockResolvedValue([
      makeTable({ id: 't1', table_number: 'T-01', capacity: 4, status: 'available' }),
      makeTable({ id: 't2', table_number: 'T-02', capacity: 2, status: 'occupied' }),
    ]);

    render(
      <MemoryRouter>
        <TablesManagerView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('T-01')).toBeDefined();
    });
    expect(screen.getByText('T-02')).toBeDefined();
    expect(mockFetchOutletTables).toHaveBeenCalledWith('outlet-1', 'token-123');
  });

  it('creates a table as owner via createTable API', async () => {
    mockAuthState = {
      token: 'token-123',
      user: makeUser('owner'),
      selectedOutlet: {
        business_id: 'biz-1',
        business_name: 'Himachal Hospitality',
        outlet_id: 'outlet-1',
        outlet_name: 'Shimla Main',
        public_slug: 'shimla-main',
        role: 'owner',
      },
      setSelectedOutletId: vi.fn(),
      logout: vi.fn(),
    };
    mockFetchOutletTables.mockResolvedValue([]);
    mockCreateTable.mockResolvedValue(makeTable({ table_number: 'T-10' }));

    render(
      <MemoryRouter>
        <TablesManagerView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('No dining tables yet.')).toBeDefined();
    });

    fireEvent.click(screen.getByText('Create the first table'));
    fireEvent.change(screen.getByPlaceholderText('e.g. T-01'), {
      target: { value: 'T-10' },
    });
    fireEvent.click(screen.getByText('Create Table'));

    await waitFor(() => {
      expect(mockCreateTable).toHaveBeenCalledWith('outlet-1', 'T-10', 4, 'token-123');
    });
  });

  it('hides create/edit controls for waiter role (read-only)', async () => {
    mockAuthState = {
      token: 'token-123',
      user: makeUser('waiter'),
      selectedOutlet: {
        business_id: 'biz-1',
        business_name: 'Himachal Hospitality',
        outlet_id: 'outlet-1',
        outlet_name: 'Shimla Main',
        public_slug: 'shimla-main',
        role: 'waiter',
      },
      setSelectedOutletId: vi.fn(),
      logout: vi.fn(),
    };
    mockFetchOutletTables.mockResolvedValue([makeTable({ table_number: 'T-03' })]);

    render(
      <MemoryRouter>
        <TablesManagerView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('T-03')).toBeDefined();
    });

    expect(screen.queryByText('+ Add Table')).toBeNull();
    expect(screen.queryByText('Edit')).toBeNull();
    expect(screen.getByText(/Read-only view/)).toBeDefined();
  });

  it('shows error state when load fails', async () => {
    mockAuthState = {
      token: 'token-123',
      user: makeUser('manager'),
      selectedOutlet: {
        business_id: 'biz-1',
        business_name: 'Himachal Hospitality',
        outlet_id: 'outlet-1',
        outlet_name: 'Shimla Main',
        public_slug: 'shimla-main',
        role: 'manager',
      },
      setSelectedOutletId: vi.fn(),
      logout: vi.fn(),
    };
    mockFetchOutletTables.mockRejectedValue(new Error('Failed to load dining tables'));

    render(
      <MemoryRouter>
        <TablesManagerView />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Failed to load dining tables')).toBeDefined();
    });
  });
});
