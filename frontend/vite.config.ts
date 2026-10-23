import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // На этой машине IPv6-loopback (::1) не принимает соединения —
    // биндимся явно на IPv4, иначе внешний браузер не достучится до localhost.
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
})
