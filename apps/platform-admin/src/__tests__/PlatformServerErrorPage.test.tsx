import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AppErrorBoundary } from '../components/errors/AppErrorBoundary';
import { ServerErrorPage } from '../components/errors/ServerErrorPage';

function Boom() {
  throw new Error('Database connection lost');
}

describe('Platform 500 page and error boundary', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    vi.restoreAllMocks();
  });

  it('renders the 500 page when a child throws and reports the error via console.error', () => {
    render(
      <AppErrorBoundary>
        <Boom />
      </AppErrorBoundary>
    );

    expect(screen.getByText('ERROR 500')).toBeDefined();
    expect(screen.getByRole('heading', { name: 'Something went wrong' })).toBeDefined();
    expect(
      screen.getByText(
        'The portal ran into an unexpected error. If you were saving a change, check its current state before trying again.'
      )
    ).toBeDefined();
    expect(screen.getByRole('button', { name: 'Reload page' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Back to Overview' })).toBeDefined();
    expect(
      screen.getByText('If this keeps happening, contact the ROMS engineering team.')
    ).toBeDefined();
    expect(consoleErrorSpy).toHaveBeenCalled();
    expect(
      consoleErrorSpy.mock.calls.some((args) =>
        args.some((arg) => arg instanceof Error && arg.message === 'Database connection lost')
      )
    ).toBe(true);
  });

  it('shows a Technical details disclosure closed by default with the real error message', () => {
    render(
      <AppErrorBoundary>
        <Boom />
      </AppErrorBoundary>
    );

    const details = document.querySelector('details') as HTMLDetailsElement;
    expect(details).not.toBeNull();
    expect(details.open).toBe(false);
    expect(screen.getByText('Technical details')).toBeDefined();
    expect(screen.getByText('Database connection lost')).toBeDefined();
  });

  it('omits the disclosure when the error has no message', () => {
    function BoomWithoutMessage() {
      throw new Error();
    }

    render(
      <AppErrorBoundary>
        <BoomWithoutMessage />
      </AppErrorBoundary>
    );

    expect(document.querySelector('details')).toBeNull();
    expect(screen.getByRole('heading', { name: 'Something went wrong' })).toBeDefined();
  });

  it('does not render the shell when the boundary catches', () => {
    render(
      <AppErrorBoundary>
        <div>
          <aside>Platform navigation</aside>
          <Boom />
        </div>
      </AppErrorBoundary>
    );

    expect(document.querySelector('aside')).toBeNull();
    expect(screen.getByRole('heading', { name: 'Something went wrong' })).toBeDefined();
  });

  it('renders without any router context', () => {
    render(<ServerErrorPage error={new Error('boom outside router')} />);

    expect(screen.getByRole('heading', { name: 'Something went wrong' })).toBeDefined();
    expect(screen.getByText('boom outside router')).toBeDefined();
  });

  it('truncates an over-long error message to about 500 characters', () => {
    const longMessage = 'x'.repeat(600);
    render(<ServerErrorPage error={new Error(longMessage)} />);

    const shown = screen.getByText(/…/);
    expect(shown.textContent).toHaveLength(501);
    expect(shown.textContent?.endsWith('…')).toBe(true);
  });
});
