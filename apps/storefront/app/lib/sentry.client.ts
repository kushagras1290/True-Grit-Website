/**
 * Sentry error reporting for the storefront — browser-only.
 *
 * Named `sentry.client.ts` on purpose: React Router's Vite plugin strips any
 * `*.client.ts` module out of the SSR bundle entirely (its exports become
 * `undefined` on the server rather than throwing), so importing it from
 * `root.tsx` — a file rendered on both server and client — can never pull
 * `@sentry/react`'s browser-only internals (it touches `window`/`document`
 * at import time) into the server bundle.
 * https://reactrouter.com/api/framework-conventions/client-modules
 *
 * A dedicated official `@sentry/react-router` package exists, but as of this
 * writing there is no supported recipe for wiring it into a plain React
 * Router v7 app deployed to Cloudflare Workers (the getsentry/sentry-javascript
 * tracker only documents Hydrogen's React-Router integration, and its own
 * "React Router v7 on Cloudflare Workers" issue is open with no finished
 * guidance — https://github.com/getsentry/sentry-javascript/issues/16130).
 * Rather than wire up unverified server-side instrumentation this project
 * cannot deploy-test, this uses the plain, well-supported `@sentry/react`
 * client SDK for browser-side reporting only.
 *
 * Gated behind `PUBLIC_SENTRY_DSN` (see `lib/public-env.ts`): unset means
 * "not configured," and both functions below become complete no-ops — no
 * `Sentry.init` call, no listeners, no network activity.
 *
 * Per the `.client` module contract, every export here is `undefined` during
 * server rendering, so callers (`root.tsx`) may only use them inside
 * `useEffect` or event handlers — never directly in a component body that
 * also renders on the server.
 */

import * as Sentry from "@sentry/react";

import { getPublicSentryDsn } from "./public-env";

let initialized = false;

/** Initialize Sentry once, browser-side only. Safe to call more than once
 * (later calls are ignored) and a no-op when no DSN is configured. */
export function initSentryClient(): void {
  if (typeof window === "undefined" || initialized) return;
  const dsn = getPublicSentryDsn();
  if (!dsn) return;
  initialized = true;
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
  });
}

/** Report a caught error (e.g. from the route `ErrorBoundary` export) to
 * Sentry. No-op when Sentry is not configured or when called server-side. */
export function captureError(error: unknown, extra?: Record<string, unknown>): void {
  if (typeof window === "undefined" || !getPublicSentryDsn()) return;
  Sentry.captureException(error, extra ? { extra } : undefined);
}
