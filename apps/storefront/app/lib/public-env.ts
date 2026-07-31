export interface PublicRuntimeEnv {
  PUBLIC_API_URL?: string;
  PUBLIC_FACEBOOK_APP_ID?: string;
}

declare global {
  interface Window {
    __TRUEGRIT_PUBLIC_ENV__?: PublicRuntimeEnv;
  }
}

const BUILD_API_URL = import.meta.env.VITE_API_URL as string | undefined;
const BUILD_FACEBOOK_APP_ID = import.meta.env.VITE_FACEBOOK_APP_ID as string | undefined;

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

// Whether the Facebook button is shown is no longer an env flag: it is an
// admin-console switch (`auth.facebook.enabled`, migration 0040) delivered
// through `lib/site-settings`. The app id below stays here because the Facebook
// SDK needs it in the browser.
