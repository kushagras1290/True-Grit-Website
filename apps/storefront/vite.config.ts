import { reactRouter } from "@react-router/dev/vite";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [tailwindcss(), reactRouter()],
  // host: true serves on both 127.0.0.1 and localhost (IPv4 + IPv6 loopback) so
  // either host works; strictPort fails loudly instead of silently drifting to
  // another port (which would break the registered Google OAuth origin).
  server: { host: true, port: 5173, strictPort: true },
});
