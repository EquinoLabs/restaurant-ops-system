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

    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeDefined();
    expect(screen.getByText('Use your ROMS team account.')).toBeDefined();
    expect(screen.getByPlaceholderText('name@company.com')).toBeDefined();
    expect(screen.getByLabelText('Password')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDefined();
  });

  it('renders the left informational panel copy', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <PlatformLoginForm />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: 'ROMS Platform Console' })).toBeDefined();
    expect(
      screen.getByText(
        'The internal control panel for the ROMS restaurant ordering and operations platform.'
      )
    ).toBeDefined();
    expect(screen.getByText('What you can do here')).toBeDefined();
    expect(screen.getByText('Manage restaurant businesses and their outlets')).toBeDefined();
    expect(screen.getByText('Review subscriptions, plans and outlet limits')).toBeDefined();
    expect(screen.getByText('Manage platform team access')).toBeDefined();
    expect(screen.getByText('Review the audit log of administrative actions')).toBeDefined();
    expect(screen.getByText('Authorised ROMS team members only.')).toBeDefined();
    expect(screen.getByText('Need access? Contact the Platform Owner.')).toBeDefined();
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

    fireEvent.change(screen.getByPlaceholderText('name@company.com'), {
      target: { value: 'wrong@example.com' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'badpass' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password')).toBeDefined();
    });

    expect(screen.getByRole('alert')).toBeDefined();
    const emailInput = screen.getByLabelText('Email') as HTMLInputElement;
    const passwordInput = screen.getByLabelText('Password') as HTMLInputElement;
    expect(emailInput.value).toBe('wrong@example.com');
    expect(passwordInput.value).toBe('');
    expect(document.activeElement).toBe(passwordInput);
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

    fireEvent.change(screen.getByPlaceholderText('name@company.com'), {
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

  it('disables the button and inputs while signing in and ignores a second submit', async () => {
    let resolveLogin!: (value: any) => void;
    const loginSpy = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveLogin = resolve;
        })
    );
    vi.spyOn(authClient, 'useAuth').mockReturnValue({
      token: null,
      user: null,
      loading: false,
      selectedOutlet: null,
      setSelectedOutletId: vi.fn(),
      login: loginSpy,
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <PlatformLoginForm />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText('name@company.com'), {
      target: { value: 'owner@roms.internal' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'pass123' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Signing in/ })).toBeDefined();
    });

    const busyButton = screen.getByRole('button', { name: /Signing in/ }) as HTMLButtonElement;
    expect(busyButton.disabled).toBe(true);
    expect((screen.getByLabelText('Email') as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText('Password') as HTMLInputElement).disabled).toBe(true);

    fireEvent.click(busyButton);
    expect(loginSpy).toHaveBeenCalledTimes(1);

    resolveLogin({
      id: 'u-owner',
      email: 'owner@roms.internal',
      display_name: 'Platform Owner',
      status: 'active',
      is_platform_admin: true,
      platform_role: 'owner',
      memberships: [],
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sign in' })).toBeDefined();
    });
    expect(loginSpy).toHaveBeenCalledTimes(1);
  });
});
