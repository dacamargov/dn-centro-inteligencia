import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// frontend lives at app/frontend; build output goes to app/frontend/dist
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/healthz': 'http://localhost:8000',
    },
  },
});
