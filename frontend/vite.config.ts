import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build-Kennung: Git-Kurz-SHA via VITE_BUILD, sonst Build-Zeitstempel.
const build =
  process.env.VITE_BUILD || new Date().toISOString().slice(0, 16).replace("T", " ");

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_BUILD__: JSON.stringify(build),
  },
});
