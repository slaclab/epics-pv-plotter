import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  server: {
    host: "0.0.0.0",
    port: 5175,
    strictPort: true,

    cors: {
      origin: [
        "http://localhost:5175",
        "http://192.168.22.4:5175",
        "http://134.79.38.36:5175",
      ],
      methods: [
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "OPTIONS",
      ],
      allowedHeaders: [
        "Content-Type",
        "Authorization",
      ],
      credentials: true,
    },
  },

  preview: {
    host: "0.0.0.0",
    port: 4173,
    strictPort: true,
  },
});
