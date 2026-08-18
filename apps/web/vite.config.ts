import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Web client for Recall. Talks to the existing FastAPI over HTTP + SSE.
// The API URL is configured per-environment via VITE_API_URL (see .env.example).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
