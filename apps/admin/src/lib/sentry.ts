/**
 * Sentry error reporting for the admin SPA.
 *
 * Gated behind `VITE_SENTRY_DSN`, read the same way `lib/api.ts` reads
 * `VITE_API_URL`: unset means "not configured." Every export here is then a
 * complete no-op — no `Sentry.init` call, no listeners attached, no network
 * activity — identical app behavior to before this module existed. There is
 * no Sentry account wired up for this project yet; an operator sets one up by
 * creating a Sentry project, copying its DSN from
 * Project Settings -> Client Keys (DSN), and setting `VITE_SENTRY_DSN` at
 * build time (a DSN's public key is meant to be client-visible, so it is safe
 * to commit or pass as a plain build var, same as `VITE_API_URL`).
 */

import * as Sentry from "@sentry/react";

const SENTRY_DSN: string = (import.meta.env.VITE_SENTRY_DSN as string | undefined) ?? "";

/** Whether a DSN is configured. Exported so callers (and tests) can assert
 * "not configured" behavior without reaching into module-private state. */
export const sentryEnabled = Boolean(SENTRY_DSN);

let initialized = false;

/**
 * Initialize Sentry. Call once, before the app renders. Safe to call more
 * than once (subsequent calls are ignored) and a complete no-op when
 * `VITE_SENTRY_DSN` is unset.
 */
export function initSentry(): void {
  if (!sentryEnabled || initialized) return;
  initialized = true;
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: import.meta.env.MODE,
  });
}

/**
 * Report a caught error (e.g. from `ErrorBoundary.componentDidCatch`) to
 * Sentry. No-op when Sentry is not configured, so callers never need their
 * own "is this set up" check.
 */
export function captureError(error: unknown, extra?: Record<string, unknown>): void {
  if (!sentryEnabled) return;
  Sentry.captureException(error, extra ? { extra } : undefined);
}
