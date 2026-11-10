import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  base: process.env.VITE_BASE ?? '/', // /Apollo/ for GitHub Pages
  plugins: [react(), tailwindcss()],
  server: { port: 5173, strictPort: true }, // the only origin the API allows
  test: { environment: 'jsdom', include: ['tests/**/*.test.{ts,tsx}'], setupFiles: ['tests/setup.ts'], restoreMocks: true },
})
