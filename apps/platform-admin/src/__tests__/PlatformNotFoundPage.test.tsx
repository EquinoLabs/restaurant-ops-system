import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { NotFoundPage } from '../components/errors/NotFoundPage';
import { PlatformAdminApp } from '../App';
import * as authClient from '@roms/api-client';

const mockAuth = (signedIn: boolean) => {
  vi.spyOn(authClient, 'useAuth').mockReturnValue({
    token: signedIn ? 'valid-token' : null,
    user: signedIn
      ? {
          id: 'u-owner',
          email: 'owner@roms.internal',
          display_name: 'Platform Owner',
          status: 'active',
          is_platform_admin: true,
          platform_role: 'owner',
          memberships: [],
        }
      : null,
    loading: false,
    selectedOutlet: null,
    setSelectedOutletId: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  });
};

const forceHistoryLength = (length: number) => {
  Object.defineProperty(window.history, 'length', { value: length, configurable: true });
};

describe('Platform 404 page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    mockAuth(false);
  });

  afterEach(() => {
    cleanup();
    window.history.replaceState({}, '', '/');
    delete (window.history as any).length;
  });

  it('renders an unknown path with the real pathname and no shell when signed out', () => {
    window.history.pushState({}, '', '/platform/does-not-exist');
    mockAuth(false);

    render(<PlatformAdminApp />);

    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeDefined();
    expect(screen.getByTitle('/platform/does-not-exist')).toBeDefined();
    expect(screen.getByText("The page you're looking for doesn't exist or has moved.")).toBeDefined();
    expect(document.querySelector('aside')).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Sign in' })).toBeNull();
  });

  it('renders an unknown path with no shell when signed in', () => {
    window.history.pushState({}, '', '/platform/unknown/child');
    mockAuth(true);

    render(<PlatformAdminApp />);

    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeDefined();
    expect(screen.getByTitle('/platform/unknown/child')).toBeDefined();
    expect(document.querySelector('aside')).toBeNull();
    expect(screen.queryByText('Checking access')).toBeNull();
  });

  it('links Back to Overview to the overview route', () => {
    render(
      <MemoryRouter initialEntries={['/no/such/page']}>
        <NotFoundPage />
      </MemoryRouter>
    );

    const link = screen.getByRole('link', { name: 'Back to Overview' });
    expect(link.getAttribute('href')).toBe('/platform/dashboard');
  });

  it('falls back to the overview route on Go back when there is no history', () => {
    forceHistoryLength(1);

    render(
      <MemoryRouter initialEntries={['/no/such/page']}>
        <Routes>
          <Route path="/no/such/page" element={<NotFoundPage />} />
          <Route path="/platform/dashboard" element={<div>Overview Target</div>} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Go back' }));
    expect(screen.getByText('Overview Target')).toBeDefined();
  });

  it('navigates back in history on Go back when previous history exists', () => {
    forceHistoryLength(3);

    render(
      <MemoryRouter initialEntries={['/platform/dashboard', '/no/such/page']}>
        <Routes>
          <Route path="/no/such/page" element={<NotFoundPage />} />
          <Route path="/platform/dashboard" element={<div>Overview Target</div>} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Go back' }));
    expect(screen.getByText('Overview Target')).toBeDefined();
  });

  it('shows a long requested path with CSS truncation and the full path in a title', () => {
    const longPath = `/platform/businesses/${'a'.repeat(120)}`;

    render(
      <MemoryRouter initialEntries={[longPath]}>
        <NotFoundPage />
      </MemoryRouter>
    );

    const pathSpan = screen.getByTitle(longPath);
    expect(pathSpan.className).toContain('truncate');
    expect(pathSpan.textContent).toBe(longPath);
  });
});
