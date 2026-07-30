/**
 * Media URL resolution.
 *
 * Uploaded images are stored by the API and served from its origin under
 * `/media/…` (R2 in production, the local filesystem in dev). The storefront
 * runs on a different origin, so those paths must be made absolute against
 * `PUBLIC_API_URL`. Storefront-relative seed assets (`/homepage-hero.png`)
 * and already-absolute URLs pass through untouched.
 */

import { getPublicApiUrl } from "./public-env";

export function mediaUrl(url: string): string;
export function mediaUrl(url: string | null | undefined): string | undefined;
export function mediaUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  if (url.startsWith("/media/")) {
    const apiUrl = getPublicApiUrl();
    if (apiUrl) return `${apiUrl}${url}`;
  }
  return url;
}
