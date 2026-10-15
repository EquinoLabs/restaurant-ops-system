import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { LoginForm } from '../features/authentication/LoginForm';
import { AuthProvider } from '@roms/api-client';
import { CategoryEditorModal } from '../features/menu-admin/CategoryEditorModal';

describe('LoginForm Component', () => {
  it('renders login form with title and input fields', () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <LoginForm />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText('ROMS Staff Portal')).toBeDefined();
    expect(screen.getByPlaceholderText('admin@himachalhospitality.com')).toBeDefined();
    expect(screen.getByPlaceholderText('••••••••')).toBeDefined();
  });
});

describe('CategoryEditorModal Component', () => {
  it('renders category form inputs and triggers onSave callback', async () => {
    const handleSave = vi.fn().mockResolvedValue(undefined);
    const handleClose = vi.fn();

    render(
      <CategoryEditorModal
        isOpen={true}
        onClose={handleClose}
        onSave={handleSave}
        category={{
          id: 'cat-1',
          outlet_id: 'outlet-1',
          name: 'Starters',
          description: 'Crispy snacks',
          sort_order: 1,
          is_active: true,
          items: [],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }}
      />
    );

    expect(screen.getByDisplayValue('Starters')).toBeDefined();
    expect(screen.getByDisplayValue('Crispy snacks')).toBeDefined();

    const saveBtn = screen.getByText('Save Changes');
    fireEvent.click(saveBtn);

    expect(handleSave).toHaveBeenCalledWith({
      name: 'Starters',
      description: 'Crispy snacks',
      sort_order: 1,
      is_active: true,
    });
  });
});
