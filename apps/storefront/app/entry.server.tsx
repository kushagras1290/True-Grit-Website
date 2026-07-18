import type { AppLoadContext, EntryContext } from "react-router";
import { ServerRouter } from "react-router";
import { isbot } from "isbot";
import { renderToReadableStream } from "react-dom/server";

import { getPublicApiUrl } from "./lib/public-env";

/**
 * Content-Security-Policy for the storefront's HTML shell. `script-src`/
 * `style-src` need 'unsafe-inline' because React Router's SSR hydration
 * payload and Tailwind's inline `style` usage aren't nonce-based here — this
 * still blocks the thing CSP mainly exists to stop (an attacker loading a
 * *remote* script), just not an inline one, which is the standard tradeoff
 * for SSR frameworks without nonce plumbing. Third-party origins below are
 * exactly what customer-auth.tsx (Google/Facebook) and commerce.ts
 * (Razorpay/PayPal) load — see those files' script/SDK URLs.
 */
function buildCsp(): string {
  const apiUrl = getPublicApiUrl();
  const connectExtra = apiUrl ? ` ${apiUrl}` : "";
  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://accounts.google.com https://connect.facebook.net https://checkout.razorpay.com https://www.paypal.com https://www.paypalobjects.com",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https:",
    "font-src 'self' data:",
    `connect-src 'self'${connectExtra} https://accounts.google.com https://graph.facebook.com https://checkout.razorpay.com https://api.razorpay.com https://lumberjack.razorpay.com https://www.paypal.com https://www.sandbox.paypal.com`,
    "frame-src https://accounts.google.com https://www.facebook.com https://staticxx.facebook.com https://checkout.razorpay.com https://api.razorpay.com https://www.paypal.com https://www.sandbox.paypal.com",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
}

// Cloudflare Workers run on the web-streams React DOM server API
// (renderToReadableStream), not the Node pipeable-stream API. Providing this
// entry explicitly prevents React Router from selecting the @react-router/node
// default entry (renderToPipeableStream), which is undefined in the Workers
// runtime and returns HTTP 500.
export default async function handleRequest(
  request: Request,
  responseStatusCode: number,
  responseHeaders: Headers,
  routerContext: EntryContext,
  _loadContext: AppLoadContext,
) {
  let shellRendered = false;
  const userAgent = request.headers.get("user-agent");

  const body = await renderToReadableStream(
    <ServerRouter context={routerContext} url={request.url} />,
    {
      onError(error: unknown) {
        responseStatusCode = 500;
        // Log streaming rendering errors from inside the shell. Don't log
        // errors encountered during initial shell rendering since they'll
        // reject and get logged in handleDocumentRequest.
        if (shellRendered) {
          console.error(error);
        }
      },
    },
  );
  shellRendered = true;

  // Ensure requests from bots and SPA Mode renders wait for all content to load
  // before responding.
  if ((userAgent && isbot(userAgent)) || routerContext.isSpaMode) {
    await body.allReady;
  }

  responseHeaders.set("Content-Type", "text/html");
  // Google Identity Services opens a sign-in popup that posts the credential
  // back via window.postMessage. "same-origin-allow-popups" keeps the opener
  // relationship so that message is delivered (otherwise browsers may block it).
  responseHeaders.set("Cross-Origin-Opener-Policy", "same-origin-allow-popups");
  responseHeaders.set("Content-Security-Policy", buildCsp());
  responseHeaders.set("X-Frame-Options", "DENY");
  responseHeaders.set("X-Content-Type-Options", "nosniff");
  responseHeaders.set("Referrer-Policy", "strict-origin-when-cross-origin");
  responseHeaders.set(
    "Strict-Transport-Security",
    "max-age=63072000; includeSubDomains; preload",
  );
  responseHeaders.set("Permissions-Policy", "geolocation=(), camera=(), microphone=()");
  return new Response(body, {
    headers: responseHeaders,
    status: responseStatusCode,
  });
}
