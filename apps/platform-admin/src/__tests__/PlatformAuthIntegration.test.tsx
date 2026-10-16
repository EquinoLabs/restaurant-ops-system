import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { PlatformLoginForm } from '../features/authentication/PlatformLoginForm';
import { RequirePlatformAdmin } from '../routes/RequirePlatformAdmin';
import * as authClient from '@roms/api-client';

describe('Platform Auth Integration Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    vi.spyOn(authClient, 'useAuth').mockReturnValue({
      token: null,
      user: null,
      loading: false,
      selectedOutlet: null,
      setSelectedOutletId: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });
  });

  it('renders login form with platform title and credentials inputs', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <PlatformLoginForm />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: 'Sign in to the platform' })).toBeDefined();
    expect(
      screen.getByText('Internal operations console for ROMS team members.')
    ).toBeDefined();
    expect(screen.getByLabelText('Password')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDefined();
  });

  it('displays error message when login fails due to invalid credentials', async () => {
    vi.spyOn(authClient, 'useAuth').mockReturnValue({
      token: null,
      user: null,
      loading: false,
      selectedOutlet: null,
      setSelectedOutletId: vi.fn(),
      login: vi.fn().mockRejectedValue(new Error('Invalid email or password')),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <PlatformLoginForm />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText('name@roms.internal'), {
      target: { value: 'wrong@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'badpass' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password')).toBeDefined();
    });
  });

  it('displays error message when user lacks platform admin role', async () => {
    const mockLogout = vi.fn();
    vi.spyOn(authClient, 'useAuth').mockReturnValue({
      token: null,
      user: null,
      loading: false,
      selectedOutlet: null,
      setSelectedOutletId: vi.fn(),
      login: vi.fn().mockResolvedValue({
        id: 'u-regular',
        email: 'staff@restaurant.com',
        display_name: 'Regular Staff',
        status: 'active',
        is_platform_admin: false,
        platform_role: null,
        memberships: [],
      }),
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <PlatformLoginForm />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText('name@roms.internal'), {
      target: { value: 'staff@restaurant.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'pass123' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => {
      expect(screen.getByText(/Access Denied: Account does not have platform administrator privileges/i)).toBeDefined();
    });
    expect(mockLogout).toHaveBeenCalled();
  });

  it('allows access through RequirePlatformAdmin for platform owner', () => {
    vi.spyOn(authClient, 'useAuth').mockReturnValue({
      token: 'valid-owner-token',
      user: {
        id: 'u-owner',
        email: 'owner@roms.com',
        display_name: 'ROMS Platform Owner',
        status: 'active',
        is_platform_admin: true,
        platform_role: 'owner',
        memberships: [],
      },
      loading: false,
      selectedOutlet: null,
      setSelectedOutletId: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/platform']}>
        <Routes>
          <Route
            path="/platform"
            element={
              <RequirePlatformAdmin>
                <div>Protected Platform Content</div>
              </RequirePlatformAdmin>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Protected Platform Content')).toBeDefined();
  });

  it('redirects unauthenticated user to /login in RequirePlatformAdmin', () => {
    vi.spyOn(authClient, 'useAuth').mockReturnValue({
      token: null,
      user: null,
      loading: false,
      selectedOutlet: null,
      setSelectedOutletId: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/platform']}>
        <Routes>
          <Route
            path="/platform"
            element={
              <RequirePlatformAdmin>
                <div>Protected Platform Content</div>
              </RequirePlatformAdmin>
            }
          />
          <Route path="/login" element={<div>Login Page Target</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.queryByText('Protected Platform Content')).toBeNull();
    expect(screen.getByText('Login Page Target')).toBeDefined();
  });
});
