import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PlatformAdminManagement } from '../features/platform-admin/PlatformAdminManagement';
import { PlatformAdminUser } from '../types/platform';
import * as apiClient from '../api/client';

describe('PlatformAdminManagement Component', () => {
  const sampleAdmins: PlatformAdminUser[] = [
    {
      id: 'user-1',
      email: 'admin1@platform.com',
      display_name: 'Primary Administrator',
      status: 'active',
      is_platform_admin: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 'user-2',
      email: 'staff2@platform.com',
      display_name: 'Secondary User',
      status: 'active',
      is_platform_admin: false,
      created_at: '2026-02-01T00:00:00Z',
      updated_at: '2026-02-01T00:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders administrator directory with user details, status badges, and action buttons', async () => {
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);

    render(<PlatformAdminManagement token="test-token" />);

    expect(screen.getByText('Loading platform administrator directory...')).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText('Platform Administrators')).toBeDefined();
      expect(screen.getByText('Primary Administrator')).toBeDefined();
      expect(screen.getByText('admin1@platform.com')).toBeDefined();
      expect(screen.getByText('Platform Administrator')).toBeDefined();
      expect(screen.getByRole('button', { name: /Revoke Access/i })).toBeDefined();

      expect(screen.getByText('Secondary User')).toBeDefined();
      expect(screen.getByText('staff2@platform.com')).toBeDefined();
      expect(screen.getByText('Standard User')).toBeDefined();
      expect(screen.getByRole('button', { name: /Grant Access/i })).toBeDefined();
    });
  });

  it('renders error state and handles retry click', async () => {
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
      expect(screen.getByText('Primary Administrator')).toBeDefined();
    });
  });

  it('opens grant/revoke confirmation modal with target user details and permits cancellation', async () => {
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Primary Administrator')).toBeDefined();
    });

    const revokeBtn = screen.getByRole('button', { name: /Revoke Access/i });
    fireEvent.click(revokeBtn);

    expect(screen.getByText('Confirm Privilege Revocation')).toBeDefined();
    expect(screen.getAllByText('admin1@platform.com').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /Confirm Revoke/i })).toBeDefined();

    const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(screen.queryByText('Confirm Privilege Revocation')).toBeNull();
    });
  });

  it('executes privilege revocation when confirmed and refreshes directory list', async () => {
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);
    const revokeSpy = vi.spyOn(apiClient, 'revokePlatformAdmin').mockResolvedValue({
      ...sampleAdmins[0],
      is_platform_admin: false,
    });

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Primary Administrator')).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: /Revoke Access/i }));
    fireEvent.click(screen.getByRole('button', { name: /Confirm Revoke/i }));

    await waitFor(() => {
      expect(revokeSpy).toHaveBeenCalledWith('user-1', 'test-token');
      expect(screen.getByText("Platform administrator privileges revoked from 'admin1@platform.com'.")).toBeDefined();
    });
  });

  it('executes privilege grant when confirmed and refreshes directory list', async () => {
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);
    const grantSpy = vi.spyOn(apiClient, 'grantPlatformAdmin').mockResolvedValue({
      ...sampleAdmins[1],
      is_platform_admin: true,
    });

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Secondary User')).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: /Grant Access/i }));
    fireEvent.click(screen.getByRole('button', { name: /Confirm Grant/i }));

    await waitFor(() => {
      expect(grantSpy).toHaveBeenCalledWith('user-2', 'test-token');
      expect(screen.getByText("Platform administrator privileges granted to 'staff2@platform.com'.")).toBeDefined();
    });
  });

  it('displays last-admin protection rejection message gracefully when backend rejects revocation', async () => {
    vi.spyOn(apiClient, 'fetchPlatformAdmins').mockResolvedValue(sampleAdmins);
    vi.spyOn(apiClient, 'revokePlatformAdmin').mockRejectedValue(
      new Error('Cannot revoke platform admin privileges from the last active platform administrator.')
    );

    render(<PlatformAdminManagement token="test-token" />);

    await waitFor(() => {
      expect(screen.getByText('Primary Administrator')).toBeDefined();
    });

    fireEvent.click(screen.getByRole('button', { name: /Revoke Access/i }));
    fireEvent.click(screen.getByRole('button', { name: /Confirm Revoke/i }));

    await waitFor(() => {
      expect(
        screen.getByText('Cannot revoke platform admin privileges from the last active platform administrator.')
      ).toBeDefined();
    });
  });
});
