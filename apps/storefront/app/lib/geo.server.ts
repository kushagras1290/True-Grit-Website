/**
 * Visitor country resolution for route loaders.
 *
 * On Cloudflare Workers the `CF-IPCountry` header carries the visitor's
 * ISO-3166 alpha-2 country. A `tg_country` cookie overrides it (useful for a
 * future manual country switcher and for local testing); local dev without
 * either falls back to `GEO_DEFAULT_COUNTRY`, then India.
 */

const COUNTRY_PATTERN = /^[A-Za-z]{2}$/;
const COUNTRY_COOKIE_PATTERN = /(?:^|;\s*)tg_country=([A-Za-z]{2})(?:;|\s|$)/;
const FALLBACK_COUNTRY = "IN";

export function resolveCountry(request: Request): string {
  const cookieHeader = request.headers.get("cookie") ?? "";
  const cookieCountry = COUNTRY_COOKIE_PATTERN.exec(cookieHeader)?.[1];
  if (cookieCountry) return cookieCountry.toUpperCase();

  // "XX" (unknown) and "T1" (Tor) are Cloudflare sentinels, not countries.
  const header = (request.headers.get("cf-ipcountry") ?? "").toUpperCase();
  if (COUNTRY_PATTERN.test(header) && header !== "XX") return header;

  const configured = (process.env.GEO_DEFAULT_COUNTRY ?? "").toUpperCase();
  if (COUNTRY_PATTERN.test(configured)) return configured;
  return FALLBACK_COUNTRY;
}
