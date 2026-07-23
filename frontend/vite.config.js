import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    watch: {
      // Docker Desktop on Windows doesn't propagate native filesystem
      // events across the bind mount, so chokidar never sees edits made
      // from the host — polling is required for HMR to pick them up.
      usePolling: true,
      interval: 300,
    },
  },
});
