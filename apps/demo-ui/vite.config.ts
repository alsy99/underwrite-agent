import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const remote = process.env.REMOTE_ACCESS === "1";
const apiPort = process.env.API_PORT || "8000";
const base = process.env.VITE_BASE_PATH || "/";

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    port: 5173,
    host: remote ? "0.0.0.0" : false,
    strictPort: true,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${apiPort}`,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  preview: {
    port: 5173,
    host: remote ? "0.0.0.0" : false,
    strictPort: true,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${apiPort}`,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
