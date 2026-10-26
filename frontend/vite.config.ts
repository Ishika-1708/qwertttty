import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend URL is NOT configured here. It is read at build time from
// VITE_API_BASE_URL (see src/services/analyticsApi.ts), so the same source
// builds for local Docker runs and for the public deployment.
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173 },
  preview: { host: true, port: 4173 },
  build: { sourcemap: true },
});
