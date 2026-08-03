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

/** The subset of Cloudflare's `IncomingRequestCfProperties` this app reads.
 *  Not part of the standard `Request` type (it is Workers-runtime-only, set
 *  by the edge before the request ever reaches this code), so it is typed
 *  narrowly here rather than pulling in the full `@cloudflare/workers-types`
 *  ambient surface for two fields. */
interface CloudflareGeoProperties {
  region?: string;
  regionCode?: string;
}

const REGION_COOKIE_PATTERN = /(?:^|;\s*)tg_region=([^;]+)/;

/**
 * State/province-level geolocation, when Cloudflare provides it.
 *
 * `region`/`regionCode` on `request.cf` are only populated on Business-plan
 * accounts and above, and are not documented as covering every country —
 * this can legitimately be `null` on a lower-tier deployment even for a real
 * Indian visitor, which is exactly why `matchIndiaRegionLocale` (geo-locale.ts)
 * is a refinement layered on top of the country-level guess, never a
 * replacement for it: state-level sharpens the guess when it is available,
 * country-level (or `Accept-Language`) still carries the visitor when it is
 * not.
 *
 * `tg_region` cookie override, same reasoning and shape as `tg_country`
 * above -- lets state-level routing be exercised in local dev and QA without
 * depending on the account tier or the tester's real location.
 */
export function resolveRegion(request: Request): {
  region: string | null;
  regionCode: string | null;
} {
  const cookieHeader = request.headers.get("cookie") ?? "";
  const cookieRegion = REGION_COOKIE_PATTERN.exec(cookieHeader)?.[1];
  if (cookieRegion) {
    const decoded = decodeURIComponent(cookieRegion).trim();
    return { region: decoded, regionCode: decoded };
  }

  const cf = (request as unknown as { cf?: CloudflareGeoProperties }).cf;
  return {
    region: cf?.region?.trim() || null,
    regionCode: cf?.regionCode?.trim() || null,
  };
}
