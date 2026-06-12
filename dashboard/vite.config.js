import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// ชี้ backend คนละเครื่องได้ เช่น dashboard บน Mac → server บน Windows:
//   VITE_API_TARGET=http://192.168.1.50:8000 npm run dev
const target = process.env.VITE_API_TARGET || 'http://localhost:8000'
const wsTarget = target.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': target,
      '/ws': { target: wsTarget, ws: true },
    },
  },
})
