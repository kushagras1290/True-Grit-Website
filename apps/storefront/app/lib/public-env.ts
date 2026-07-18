export interface PublicRuntimeEnv {
  PUBLIC_API_URL?: string;
  PUBLIC_FACEBOOK_APP_ID?: string;
  PUBLIC_FACEBOOK_LOGIN_VISIBLE?: string;
  PUBLIC_SENTRY_DSN?: string;
}

declare global {
  interface Window {
    __TRUEGRIT_PUBLIC_ENV__?: PublicRuntimeEnv;
  }
}

const BUILD_API_URL = import.meta.env.VITE_API_URL as string | undefined;
const BUILD_FACEBOOK_APP_ID = import.meta.env.VITE_FACEBOOK_APP_ID as string | undefined;
const BUILD_FACEBOOK_LOGIN_VISIBLE = import.meta.env.VITE_FACEBOOK_LOGIN_VISIBLE as
  string | undefined;
const BUILD_SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined;

function normalizeUrl(value: string | undefined): string {
  return value?.trim().replace(/\/+$/, "") ?? "";
}

function isLoopbackUrl(value: string): boolean {
  try {
    const hostname = new URL(value).hostname;
    return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
  } catch {
    return false;
  }
}

function isLocalBrowserOrigin(): boolean {
  if (typeof window === "undefined") return false;
  const { hostname } = window.location;
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function processEnv(name: string): string | undefined {
  if (typeof process === "undefined") return undefined;
  return process.env[name];
}

export function getPublicApiUrl(): string {
  if (typeof window !== "undefined") {
    const runtimeApiUrl = normalizeUrl(window.__TRUEGRIT_PUBLIC_ENV__?.PUBLIC_API_URL);
    if (runtimeApiUrl) return runtimeApiUrl;

    const buildApiUrl = normalizeUrl(BUILD_API_URL);
    if (buildApiUrl && (!isLoopbackUrl(buildApiUrl) || isLocalBrowserOrigin())) return buildApiUrl;
    return "";
  }

  return normalizeUrl(processEnv("PUBLIC_API_URL") || BUILD_API_URL);
}

export function hasPublicApiUrl(): boolean {
  return Boolean(getPublicApiUrl());
}

export function getPublicFacebookAppId(): string {
  if (typeof window !== "undefined") {
    return (
      normalizeUrl(window.__TRUEGRIT_PUBLIC_ENV__?.PUBLIC_FACEBOOK_APP_ID) ||
      normalizeUrl(BUILD_FACEBOOK_APP_ID)
    );
  }
  return normalizeUrl(processEnv("PUBLIC_FACEBOOK_APP_ID") || BUILD_FACEBOOK_APP_ID);
}

function isEnabledFlag(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "true";
}

export function isFacebookLoginVisible(): boolean {
  if (typeof window !== "undefined") {
    return isEnabledFlag(
      window.__TRUEGRIT_PUBLIC_ENV__?.PUBLIC_FACEBOOK_LOGIN_VISIBLE || BUILD_FACEBOOK_LOGIN_VISIBLE,
    );
  }
  return isEnabledFlag(processEnv("PUBLIC_FACEBOOK_LOGIN_VISIBLE") || BUILD_FACEBOOK_LOGIN_VISIBLE);
}

/** Sentry DSN, or "" when error reporting is not configured. Same
 * runtime-var-first, build-var-fallback resolution as `getPublicApiUrl` /
 * `getPublicFacebookAppId`, so a deployed Worker's `PUBLIC_SENTRY_DSN` var
 * always wins over whatever was baked in at build time. */
export function getPublicSentryDsn(): string {
  if (typeof window !== "undefined") {
    return (
      normalizeUrl(window.__TRUEGRIT_PUBLIC_ENV__?.PUBLIC_SENTRY_DSN) ||
      normalizeUrl(BUILD_SENTRY_DSN)
    );
  }
  return normalizeUrl(processEnv("PUBLIC_SENTRY_DSN") || BUILD_SENTRY_DSN);
}
