/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@roms/shared-types': resolve(__dirname, 'packages/shared-types/src'),
      '@roms/api-client': resolve(__dirname, 'packages/api-client/src'),
      '@roms/ui': resolve(__dirname, 'packages/ui/src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['apps/**/*.test.tsx', 'packages/**/*.test.ts'],
  },
});
