import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Built straight into the Python package so one uvicorn process serves the UI
// and the API from one address. In development the API runs on 8000 and Vite
// proxies /api to it.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../src/nlq/static",
    emptyOutDir: true,
  },
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
