import { reactRouter } from "@react-router/dev/vite";
import { cloudflare } from "@cloudflare/vite-plugin";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  // The Cloudflare plugin runs the SSR build inside the Workers runtime so local
  // dev matches production. It reads apps/storefront/wrangler.jsonc for the
  // Worker name, assets, and bindings.
  plugins: [cloudflare({ viteEnvironment: { name: "ssr" } }), tailwindcss(), reactRouter()],
  environments: {
    ssr: {
      build: {
        outDir: "dist/server",
      },
    },
  },
  // host: true serves on both 127.0.0.1 and localhost (IPv4 + IPv6 loopback) so
  // either host works; strictPort fails loudly instead of silently drifting to
  // another port (which would break the registered Google OAuth origin).
  server: { host: true, port: 5173, strictPort: true },
});
