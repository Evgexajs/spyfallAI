import { defineConfig } from 'vite'
import { resolve } from 'path'

export default defineConfig({
  resolve: {
    alias: {
      '@parser': resolve(__dirname, 'src/parser'),
      '@player': resolve(__dirname, 'src/player'),
      '@render': resolve(__dirname, 'src/render'),
      '@ui': resolve(__dirname, 'src/ui'),
      '@config': resolve(__dirname, 'src/config'),
    },
  },
  server: {
    port: 5173,
  },
})
