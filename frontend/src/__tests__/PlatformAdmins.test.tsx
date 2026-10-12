import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PlatformAdminManagement, getPlatformRoleInfo } from '../features/platform-admin/PlatformAdminManagement';
import { PlatformAdminUser } from '../types/platform';
import * as apiClient from '../api/client';
import * as authContext from '../features/authentication/AuthContext';

describe('getPlatformRoleInfo helper function', () => {
  it('correctly maps explicit platform roles according to Decision 2', () => {
    const ownerUser = { id: '1', email: 'o@test.com', display_name: 'Owner', status: 'active', is_platform_admin: true, platform_role: 'owner', created_at: '', updated_at: '' };
    const adminUser = { id: '2', email: 'a@test.com', display_name: 'Admin', status: 'active', is_platform_admin: true, platform_role: 'admin', created_at: '', updated_at: '' };
    const opUser = { id: '3', email: 'op@test.com', display_name: 'Op', status: 'active', is_platform_admin: false, platform_role: 'operator', created_at: '', updated_at: '' };

    expect(getPlatformRoleInfo(ownerUser).label).toBe('Platform Owner');
    expect(getPlatformRoleInfo(adminUser).label).toBe('Platform Admin');
    expect(getPlatformRoleInfo(opUser).label).toBe('Platform Operator');
  });

  it('correctly displays Platform Admin (Legacy) when platform_role is null/undefined and is_platform_admin is true', () => {
    const legacyUserNull = { id: '1', email: 'l1@test.com', display_name: 'Legacy Null', status: 'active', is_platform_admin: true, platform_role: null, created_at: '', updated_at: '' };
    const legacyUserUndefined = { id: '2', email: 'l2@test.com', display_name: 'Legacy Undefined', status: 'active', is_platform_admin: true, created_at: '', updated_at: '' };

    expect(getPlatformRoleInfo(legacyUserNull).label).toBe('Platform Admin (Legacy)');
    expect(getPlatformRoleInfo(legacyUserUndefined).label).toBe('Platform Admin (Legacy)');
  });

  it('fails closed to Standard User for unrecognized roles or non-admins', () => {
    const standardUser = { id: '1', email: 's@test.com', display_name: 'Standard', status: 'active', is_platform_admin: false, platform_role: null, created_at: '', updated_at: '' };
    const unrecognizedRoleUser = { id: '2', email: 'u@test.com', display_name: 'Unrecognized', status: 'active', is_platform_admin: false, platform_role: 'invalid_role', created_at: '', updated_at: '' };

    expect(getPlatformRoleInfo(standardUser).label).toBe('Standard User');
    expect(getPlatformRoleInfo(unrecognizedRoleUser).label).toBe('Standard User');
  });
});

describe('PlatformAdminManagement Component', () => {
  const sampleAdmins: PlatformAdminUser[] = [
    {
      id: 'user-owner',
      email: 'owner@platform.com',
      display_name: 'Platform Owner User',
      status: 'active',
      is_platform_admin: true,
      platform_role: 'owner',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 'user-admin',
      email: 'admin@platform.com',
      display_name: 'Platform Admin User',
      status: 'active',
      is_platform_admin: true,
      platform_role: 'admin',
      created_at: '2026-02-01T00:00:00Z',
      updated_at: '2026-02-01T00:00:00Z',
    },
    {
      id: 'user-legacy',
      email: 'legacy@platform.com',
      display_name: 'Legacy Admin User',
      status: 'active',
      is_platform_admin: true,
      platform_role: null,
      created_at: '2026-02-15T00:00:00Z',
      updated_at: '2026-02-15T00:00:00Z',
    },
    {
      id: 'user-op',
      email: 'operator@platform.com',
      display_name: 'Platform Operator User',
      status: 'active',
      is_platform_admin: false,
      platform_role: 'operator',
      created_at: '2026-03-01T00:00:00Z',
      updated_at: '2026-03-01T00:00:00Z',
    },
    {
      id: 'user-standard',
      email: 'standard@platform.com',
      display_name: 'Standard Staff User',
      status: 'active',
      is_platform_admin: false,
      platform_role: null,
      created_at: '2026-03-10T00:00:00Z',
      updated_at: '2026-03-10T00:00:00Z',
    },
  ];

  const mockAuthUser = (role?: string | null, isPlatformAdmin: boolean = true, userId: string = 'user-owner') => {
    vi.spyOn(authContext, 'useAuth').mockReturnValue({
      token: 'test-token',
      user: {
        id: userId,
        email: 'logged_in@platform.com',
        display_name: 'Authenticated User',
        status: 'active',
        is_platform_admin: isPlatformAdmin,
        platform_role: role,
        memberships: [],
      },
      loading: false,
      selectedOutlet: null,
      setSelectedOutletId: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders directory with distinct three-tier role badges and legacy compatibility badge for Owner', async () => {
    mockAuthUser('owner', true, 'user-owner');
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);

    render(<PlatformAdminManagement token="test-token" />);

    expect(screen.getByText('Loading platform administrator directory...')).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText('Platform Administrators')).toBeDefined();
      expect(screen.getByText('Platform Owner User')).toBeDefined();
      expect(screen.getByText('Platform Owner')).toBeDefined();

      expect(screen.getByText('Platform Admin User')).toBeDefined();
      expect(screen.getByText('Platform Admin')).toBeDefined();

      expect(screen.getByText('Legacy Admin User')).toBeDefined();
      expect(screen.getByText('Platform Admin (Legacy)')).toBeDefined();

      expect(screen.getByText('Platform Operator User')).toBeDefined();
      expect(screen.getByText('Platform Operator')).toBeDefined();

      expect(screen.getByText('Standard Staff User')).toBeDefined();
      expect(screen.getByText('Standard User')).toBeDefined();
    });
  });

  it('allows Platform Owner to view active Grant and Revoke action buttons and open confirmation modal', async () => {
    mockAuthUser('owner', true, 'user-owner');
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Platform Admin User')).toBeDefined();
    });

    // Current user (user-owner) has "Current User (Self)" disabled indicator
    expect(screen.getByText('Current User (Self)')).toBeDefined();

    // Owner sees active Revoke Access button for other admins
    const revokeButtons = screen.getAllByRole('button', { name: /Revoke Access/i });
    expect(revokeButtons.length).toBeGreaterThan(0);

    // Owner sees active Grant Access button for non-admins
    const grantButtons = screen.getAllByRole('button', { name: /Grant Access/i });
    expect(grantButtons.length).toBeGreaterThan(0);

    // Clicking Revoke opens confirmation modal
    fireEvent.click(revokeButtons[0]);
    expect(screen.getByText('Confirm Privilege Revocation')).toBeDefined();

    // Clicking cancel closes modal
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    await waitFor(() => {
      expect(screen.queryByText('Confirm Privilege Revocation')).toBeNull();
    });
  });

  it('executes privilege revocation when confirmed by Owner and refreshes list', async () => {
    mockAuthUser('owner', true, 'user-owner');
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);
    const revokeSpy = vi.spyOn(apiClient, 'revokePlatformAdmin').mockResolvedValue({
      ...sampleAdmins[1],
      is_platform_admin: false,
    });

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Platform Admin User')).toBeDefined();
    });

    fireEvent.click(screen.getAllByRole('button', { name: /Revoke Access/i })[0]);
    fireEvent.click(screen.getByRole('button', { name: /Confirm Revoke/i }));

    await waitFor(() => {
      expect(revokeSpy).toHaveBeenCalledWith('user-admin', 'test-token');
      expect(screen.getByText("Platform administrator privileges revoked from 'admin@platform.com'.")).toBeDefined();
    });
  });

  it('executes privilege grant when confirmed by Owner and refreshes list', async () => {
    mockAuthUser('owner', true, 'user-owner');
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);
    const grantSpy = vi.spyOn(apiClient, 'grantPlatformAdmin').mockResolvedValue({
      ...sampleAdmins[3],
      is_platform_admin: true,
    });

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Platform Operator User')).toBeDefined();
    });

    fireEvent.click(screen.getAllByRole('button', { name: /Grant Access/i })[0]);
    fireEvent.click(screen.getByRole('button', { name: /Confirm Grant/i }));

    await waitFor(() => {
      expect(grantSpy).toHaveBeenCalledWith('user-op', 'test-token');
      expect(screen.getByText("Platform administrator privileges granted to 'operator@platform.com'.")).toBeDefined();
    });
  });

  it('restricts Non-Owner Admin: displays directory in read-only mode with Requires Owner indicator', async () => {
    // Authenticated user is a Platform Admin (not Owner)
    mockAuthUser('admin', true, 'user-admin');
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Platform Admin User')).toBeDefined();
    });

    // Zero active Grant or Revoke buttons should be present
    expect(screen.queryByRole('button', { name: /Revoke Access/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /Grant Access/i })).toBeNull();

    // "Requires Owner" indicators are displayed for non-self rows
    const requiresOwnerBadges = screen.getAllByText('Requires Owner');
    expect(requiresOwnerBadges.length).toBeGreaterThan(0);
    expect(requiresOwnerBadges[0].className).toContain('cursor-not-allowed');

    // Self indicator remains present
    expect(screen.getByText('Current User (Self)')).toBeDefined();
  });

  it('restricts Legacy Admin (platform_role: null, is_platform_admin: true) to read-only mode with Requires Owner', async () => {
    mockAuthUser(null, true, 'user-legacy');
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Legacy Admin User')).toBeDefined();
    });

    expect(screen.queryByRole('button', { name: /Revoke Access/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /Grant Access/i })).toBeNull();
    expect(screen.getAllByText('Requires Owner').length).toBeGreaterThan(0);
  });

  it('fails closed to read-only mode when current user role is missing, unrecognized, or null', async () => {
    mockAuthUser('unrecognized_role', false, 'user-unknown');
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Platform Admin User')).toBeDefined();
    });

    expect(screen.queryByRole('button', { name: /Revoke Access/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /Grant Access/i })).toBeNull();
    expect(screen.getAllByText('Requires Owner').length).toBeGreaterThan(0);
  });

  it('renders Access Restricted guard and skips API call when Operator navigates directly', async () => {
    mockAuthUser('operator', false, 'user-op');
    const fetchSpy = vi.spyOn(apiClient, 'fetchPlatformAdmins');

    render(<PlatformAdminManagement token="test-token" />);

    expect(screen.getByText('Access Restricted: Platform Operator')).toBeDefined();
    expect(
      screen.getByText(/Platform Operators do not have administrative directory access/i)
    ).toBeDefined();

    // API should not even be called
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(screen.queryByText('Platform Administrators')).toBeNull();
  });

  it('renders zero-owner offline banner when API returns HTTP 503 PLATFORM_OWNER_NOT_INITIALIZED', async () => {
    mockAuthUser('admin', true, 'user-admin');
    const err = new Error('Platform Owner has not been initialized. Governance operations are unavailable.') as Error & { status?: number; code?: string };
    err.status = 503;
    err.code = 'PLATFORM_OWNER_NOT_INITIALIZED';

    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockRejectedValue(err);

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Platform Governance Offline (Zero-Owner State)')).toBeDefined();
      expect(
        screen.getByText(/Platform Owner has not been initialized/i)
      ).toBeDefined();
    });
  });

  it('renders permission denied banner when API returns HTTP 403 Forbidden', async () => {
    mockAuthUser('admin', true, 'user-admin');
    const err = new Error('Platform administrator privileges are required') as Error & { status?: number; code?: string };
    err.status = 403;

    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockRejectedValue(err);

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Permission Denied')).toBeDefined();
      expect(screen.getByText(/Platform administrator privileges are required/i)).toBeDefined();
    });
  });

  it('handles general network errors with retry button', async () => {
    mockAuthUser('admin', true, 'user-admin');
    const fetchSpy = vi
      .spyOn(apiClient, 'fetchPlatformAdmins')
      .mockRejectedValueOnce(new Error('Network connection failed'))
      .mockResolvedValueOnce(sampleAdmins);

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Error Loading Administrator Directory')).toBeDefined();
      expect(screen.getByText('Network connection failed')).toBeDefined();
    });

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledTimes(2);
      expect(screen.getByText('Platform Admin User')).toBeDefined();
    });
  });

  it('displays last-admin protection rejection message gracefully in action modal', async () => {
    mockAuthUser('owner', true, 'user-owner');
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);
    vi.spyOn(apiClient, 'revokePlatformAdmin').mockRejectedValue(
      new Error('Cannot revoke platform admin privileges from the last active platform administrator.')
    );

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Platform Admin User')).toBeDefined();
    });

    fireEvent.click(screen.getAllByRole('button', { name: /Revoke Access/i })[0]);
    fireEvent.click(screen.getByRole('button', { name: /Confirm Revoke/i }));

    await waitFor(() => {
      expect(
        screen.getByText('Cannot revoke platform admin privileges from the last active platform administrator.')
      ).toBeDefined();
    });
  });
});
