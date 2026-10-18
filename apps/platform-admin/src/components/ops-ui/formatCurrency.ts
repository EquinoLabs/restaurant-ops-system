/**
 * Standard currency formatting utilities following docs/design/DESIGN.md:
 * - INR: ₹ symbol without space, standard Indian grouping (en-IN, e.g. ₹1,50,000.00)
 * - Non-INR: Native currency symbol with Western grouping (e.g. $150,000.00, €150,000.00)
 * - Tabular figures (tnum) via Inter typography.
 */

export function formatCurrency(
  amount: number | null | undefined,
  currencyCode: string = 'INR'
): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return '—';
  }

  const normalizedCode = (currencyCode || 'INR').trim().toUpperCase();

  try {
    const locale = normalizedCode === 'INR' ? 'en-IN' : 'en-US';
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: normalizedCode,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    // Fallback if currency code is unrecognised by Intl
    const formattedNum = Number(amount).toLocaleString(normalizedCode === 'INR' ? 'en-IN' : 'en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return `${normalizedCode} ${formattedNum}`;
  }
}
