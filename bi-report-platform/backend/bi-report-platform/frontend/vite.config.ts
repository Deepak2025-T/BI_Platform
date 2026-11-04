import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, calls to /api go to the FastAPI server on port 8000.
// This means no CORS problems and no hard-coded URLs in the React code.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
