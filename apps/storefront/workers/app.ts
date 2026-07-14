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
    return requestHandler(request, {
      cloudflare: { env, ctx },
    });
  },
} satisfies ExportedHandler<Env>;
