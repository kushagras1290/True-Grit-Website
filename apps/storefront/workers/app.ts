import { createRequestHandler } from "react-router";

// Make the Cloudflare `env` (vars, secrets, bindings) available to React Router
// loaders/actions via `context.cloudflare.env`. Server code that reads
// `process.env.*` also works because `nodejs_compat` populates `process.env`
// from the Worker's vars/secrets (see wrangler.jsonc).
declare module "react-router" {
  export interface AppLoadContext {
    cloudflare: {
      env: Env;
      ctx: ExecutionContext;
    };
  }
}

const requestHandler = createRequestHandler(
  () => import("virtual:react-router/server-build"),
  import.meta.env.MODE,
);

export default {
  async fetch(request, env, ctx) {
    // Only set in production (wrangler.jsonc env.production.vars) -- redirects
    // every non-canonical hostname routed to this Worker (currently just
    // www.truegritin.com) to the canonical domain before rendering anything,
    // so the API's CORS allow-list only ever needs to trust one storefront
    // origin and search engines see one canonical URL per page.
    const canonicalHost = env.CANONICAL_HOST;
    if (canonicalHost) {
      const url = new URL(request.url);
      if (url.hostname !== canonicalHost) {
        url.hostname = canonicalHost;
        return Response.redirect(url.toString(), 301);
      }
    }
    return requestHandler(request, {
      cloudflare: { env, ctx },
    });
  },
} satisfies ExportedHandler<Env>;
