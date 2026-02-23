import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/time': 'http://localhost:8000',
      '/concept': 'http://localhost:8000',
      '/contemplate': 'http://localhost:8000',
      '/stream': 'http://localhost:8000',
      '/mind': 'http://localhost:8000',
      '/history': 'http://localhost:8000',
    },
  },
})
