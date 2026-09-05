import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  // GitHub Pages serves a project site from /<repo>/, so assets need that prefix.
  // Read it from the environment rather than a CLI flag: MSYS shells rewrite a
  // leading-slash argument into a Windows path.
  base: process.env.VITE_BASE_PATH ?? "/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
