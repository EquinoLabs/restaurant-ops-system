import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    resolve(__dirname, 'apps/**/*.{html,js,ts,jsx,tsx}'),
    resolve(__dirname, 'packages/**/*.{html,js,ts,jsx,tsx}'),
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#fffbeb',
          100: '#fef3c7',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          900: '#78350f',
        },
        ops: {
          canvas: '#F6F7F9',
          surface: '#FFFFFF',
          border: '#E3E6EA',
          divider: '#EEF0F3',
          text: {
            primary: '#1F2933',
            secondary: '#616E7C',
            disabled: '#9AA5B1',
          },
          accent: {
            DEFAULT: '#2554C7',
            hover: '#1D44A6',
            active: '#183A8F',
            focus: 'rgba(37, 84, 199, 0.24)',
          },
          status: {
            'active-bg': '#E6F4EC',
            'active-text': '#1B7F4B',
            'pending-bg': '#FFF4DB',
            'pending-text': '#8A5A00',
            'critical-bg': '#FDECEA',
            'critical-text': '#B42318',
            'neutral-bg': '#EEF0F3',
            'neutral-text': '#52606D',
          },
          error: '#B42318',
        },
      },
      boxShadow: {
        'ops-l1': '0px 2px 4px rgba(31, 41, 51, 0.04), 0px 4px 8px rgba(31, 41, 51, 0.06)',
        'ops-l2': '0px 8px 16px rgba(31, 41, 51, 0.08), 0px 16px 24px rgba(31, 41, 51, 0.06)',
      },
    },
  },
  plugins: [],
};
