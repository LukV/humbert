import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The web app is a plain SPA served by the Python backend in production.
// In dev, proxy /api to the Python process so the two halves talk over one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
