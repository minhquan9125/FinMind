import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { realDataGuard } from "./build/realDataGuard.js";

export default defineConfig({
  plugins: [react(), realDataGuard()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
