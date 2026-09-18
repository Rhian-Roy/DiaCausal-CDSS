import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // `@/components/...` means `src/components/...` (shadcn/ui expects this alias).
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    strictPort: true,
    // The browser only ever talks to Vite (port 5173). Anything under /api is
    // forwarded to the FastAPI backend, so there is no CORS setup to get wrong.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
