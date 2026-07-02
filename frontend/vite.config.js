import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Docker Desktop on Windows doesn't reliably forward native filesystem
    // change events from bind mounts into the Linux container, so Vite's
    // watcher silently misses edits without polling.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});
