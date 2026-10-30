import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, calls to /api go to the FastAPI server on port 8000.
// This means no CORS problems and no hard-coded URLs in the React code.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 127.0.0.1, not localhost: on Windows "localhost" resolves to ::1 first, and uvicorn
      // binds IPv4 only by default, which makes every call fail with ECONNREFUSED.
      // The timeouts allow for slow local AI models; without them the proxy cuts the call short.
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        timeout: 320000,
        proxyTimeout: 320000,
      },
    },
  },
});
