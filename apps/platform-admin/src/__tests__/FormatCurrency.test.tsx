import { describe, it, expect } from 'vitest';
import { formatCurrency } from '../components/ops-ui/formatCurrency';

describe('formatCurrency', () => {
  it('formats INR using en-IN grouping and ₹ symbol without trailing space', () => {
    expect(formatCurrency(150000, 'INR')).toBe('₹1,50,000.00');
    expect(formatCurrency(14580, 'INR')).toBe('₹14,580.00');
    expect(formatCurrency(0, 'INR')).toBe('₹0.00');
  });

  it('formats non-INR currencies using Western grouping and appropriate symbol', () => {
    expect(formatCurrency(150000, 'USD')).toBe('$150,000.00');
    expect(formatCurrency(150000, 'EUR')).toBe('€150,000.00');
    expect(formatCurrency(150000, 'GBP')).toBe('£150,000.00');
  });

  it('handles null, undefined, or NaN gracefully with em-dash', () => {
    expect(formatCurrency(null, 'INR')).toBe('—');
    expect(formatCurrency(undefined, 'USD')).toBe('—');
    expect(formatCurrency(Number.NaN, 'INR')).toBe('—');
  });

  it('defaults to INR when currency code is omitted', () => {
    expect(formatCurrency(5000)).toBe('₹5,000.00');
  });
});
