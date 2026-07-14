import type { Config } from "@react-router/dev/config";

export default {
  ssr: true,
  // Align React Router's build directory with the output directory the
  // @cloudflare/vite-plugin writes to (dist/), so the SSR build can locate the
  // client manifest at dist/client/.vite/manifest.json.
  buildDirectory: "dist",
} satisfies Config;
