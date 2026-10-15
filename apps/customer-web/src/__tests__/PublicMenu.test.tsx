import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MenuItemCard } from '../features/public-menu/MenuItemCard';
import { MenuItem } from '@roms/shared-types';

describe('MenuItemCard Component', () => {
  const sampleItem: MenuItem = {
    id: '123',
    name: 'Himachali Trout Fry',
    description: 'Fresh river fish',
    price: 450.0,
    image_url: null,
    is_available: true,
    sort_order: 1,
  };

  it('renders item name, description, and price correctly', () => {
    render(<MenuItemCard item={sampleItem} currency="INR" />);
    expect(screen.getByText('Himachali Trout Fry')).toBeDefined();
    expect(screen.getByText('Fresh river fish')).toBeDefined();
    expect(screen.getByText('₹450.00')).toBeDefined();
  });

  it('renders sold out badge when item is unavailable', () => {
    const unavailableItem = { ...sampleItem, is_available: false };
    render(<MenuItemCard item={unavailableItem} currency="INR" />);
    expect(screen.getByText('Sold Out')).toBeDefined();
  });
});
