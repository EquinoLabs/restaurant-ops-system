/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  root: resolve(__dirname),
  plugins: [react()],
  resolve: {
    alias: {
      '@roms/shared-types': resolve(__dirname, '../../packages/shared-types/src'),
      '@roms/api-client': resolve(__dirname, '../../packages/api-client/src'),
      '@roms/ui': resolve(__dirname, '../../packages/ui/src'),
    },
  },
  server: {
    port: 5176,
    host: true,
  },
  build: {
    outDir: resolve(__dirname, 'dist'),
    emptyOutDir: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
  },
});
