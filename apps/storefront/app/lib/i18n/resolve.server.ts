/**
 * Server-side locale resolution and the cookie that remembers it.
 *
 * Resolved in the root loader so the very first byte of HTML is already in the
 * right language. A client-side switch would paint English, hydrate, then
 * repaint — the exact flash this feature exists to remove — and would leave
 * crawlers, which do not run JavaScript, seeing only English.
 */

import { resolveCountry, resolveRegion } from "../geo.server";
import { matchCountryLocale, matchIndiaRegionLocale } from "./geo-locale";
import {
  DEFAULT_LOCALE,
  LOCALES,
  LOCALE_COOKIE_MAX_AGE_SECONDS,
  LOCALE_COOKIE_NAME,
  getLocale,
  type LocaleDefinition,
} from "./locales";

function matchFrom(locales: readonly LocaleDefinition[], code: string | null | undefined) {
  if (!code) return null;
  const normalized = code.trim().toLowerCase();
  if (!normalized) return null;
  const exact = locales.find((entry) => entry.code.toLowerCase() === normalized);
  if (exact) return exact;
  const base = normalized.split("-")[0]!;
  if (base === "zh") {
    const subtags = new Set(normalized.split("-").slice(1));
    const traditional = ["hant", "tw", "hk", "mo"].some((subtag) => subtags.has(subtag));
    return (
      locales.find((entry) => entry.code.toLowerCase() === (traditional ? "zh-hant" : "zh-hans")) ??
      null
    );
  }
  return locales.find((entry) => entry.code.split("-")[0]!.toLowerCase() === base) ?? null;
}

function matchHeader(locales: readonly LocaleDefinition[], header: string | null) {
  if (!header) return null;
  const candidates = header
    .split(",")
    .map((part, index) => {
      const [code, ...parameters] = part.trim().split(";");
      const qRaw = parameters.find((parameter) => parameter.trim().startsWith("q="));
      const q = qRaw ? Number(qRaw.trim().slice(2)) : 1;
      return { code, q: Number.isFinite(q) ? q : 0, index };
    })
    .filter((entry) => entry.code && entry.code !== "*" && entry.q > 0)
    .sort((left, right) => right.q - left.q || left.index - right.index);
  for (const candidate of candidates) {
    const match = matchFrom(locales, candidate.code);
    if (match) return match;
  }
  return null;
}

/** Query parameter that overrides everything, for links that must land in a
 *  known language (a campaign, a QR code on a Hindi leaflet). */
export const LOCALE_QUERY_PARAM = "lang";

function readCookie(header: string | null, name: string): string | null {
  if (!header) return null;
  for (const part of header.split(";")) {
    const index = part.indexOf("=");
    if (index < 0) continue;
    if (part.slice(0, index).trim() !== name) continue;
    try {
      return decodeURIComponent(part.slice(index + 1).trim());
    } catch {
      // A malformed percent-escape is a corrupt cookie, not a crash: fall
      // through to the next source rather than 500 the whole page.
      return null;
    }
  }
  return null;
}

/** Where a resolved locale came from — the root loader uses this to decide
 *  whether the visitor gets a "we picked this for you" prompt (see
 *  `LanguageSuggestionPrompt`). Only `"geo"` ever triggers one: a `"query"` or
 *  `"cookie"` locale is something the visitor already chose, and a `"header"`
 *  locale is what their own browser explicitly asked for — neither needs
 *  second-guessing. */
export type LocaleSource = "query" | "cookie" | "header" | "geo" | "default";

export interface ResolvedLocale {
  locale: LocaleDefinition;
  source: LocaleSource;
}

/**
 * Which language to render, in priority order:
 *
 *   1. `?lang=` — an explicit link, and the switcher's no-JavaScript path.
 *   2. The cookie — what this visitor chose last time.
 *   3. `Accept-Language`, when it names a real language — q-values honoured.
 *   4. The visitor's Indian state (Cloudflare's edge geo region, when the
 *      account tier and the request both carry it) for a visitor in India —
 *      a Punjab visitor and a Tamil Nadu visitor get different guesses even
 *      though both are country "IN", where step 5 alone could not tell them
 *      apart. Falls through silently when region data is unavailable.
 *   5. The visitor's country (Cloudflare's edge geo), when `Accept-Language`
 *      has no supported language.
 *   6. English.
 *
 * The browser is consulted before geo whenever it names a supported language:
 * an explicit preference must survive a country guess that disagrees with it.
 * Step 4 is why the switch is announced rather than silent: a guess from an IP
 * address is still a guess, not a preference the visitor stated.
 */
export function resolveLocale(
  request: Request,
  locales: readonly LocaleDefinition[] = LOCALES,
): ResolvedLocale {
  const url = new URL(request.url);
  const fromQuery = matchFrom(locales, url.searchParams.get(LOCALE_QUERY_PARAM));
  if (fromQuery) return { locale: fromQuery, source: "query" };

  const fromCookie = matchFrom(
    locales,
    readCookie(request.headers.get("cookie"), LOCALE_COOKIE_NAME),
  );
  if (fromCookie) return { locale: fromCookie, source: "cookie" };

  const fromHeader = matchHeader(locales, request.headers.get("accept-language"));
  if (fromHeader) return { locale: fromHeader, source: "header" };

  const country = resolveCountry(request);
  if (country === "IN") {
    const { region, regionCode } = resolveRegion(request);
    const fromRegion = matchIndiaRegionLocale(region, regionCode);
    if (fromRegion && matchFrom(locales, fromRegion.code) && fromRegion.code !== DEFAULT_LOCALE) {
      return { locale: fromRegion, source: "geo" };
    }
  }

  const fromGeo = matchCountryLocale(country);
  if (fromGeo && matchFrom(locales, fromGeo.code) && fromGeo.code !== DEFAULT_LOCALE) {
    return { locale: fromGeo, source: "geo" };
  }

  // Non-null: DEFAULT_LOCALE is always a registered locale.
  return {
    locale: matchFrom(locales, DEFAULT_LOCALE) ?? getLocale(DEFAULT_LOCALE)!,
    source: "default",
  };
}

/**
 * A `Set-Cookie` value remembering `locale`.
 *
 * Not `HttpOnly`: this is a display preference with no security value, and
 * leaving it readable lets client code (and anyone debugging) see the state
 * without a round trip. `SameSite=Lax` so following a link into the site from
 * elsewhere still arrives in the chosen language. Not `Secure`, because local
 * development is served over plain HTTP and a preference cookie that silently
 * fails to set there is a confusing thing to debug; there is nothing here worth
 * protecting from a network observer who can already read the rendered page.
 */
export function localeCookie(
  locale: string,
  locales: readonly LocaleDefinition[] = LOCALES,
): string {
  const safe = matchFrom(locales, locale)?.code ?? DEFAULT_LOCALE;
  return [
    `${LOCALE_COOKIE_NAME}=${encodeURIComponent(safe)}`,
    "Path=/",
    `Max-Age=${LOCALE_COOKIE_MAX_AGE_SECONDS}`,
    "SameSite=Lax",
  ].join("; ");
}

/**
 * A safe place to send the visitor back to after switching language.
 *
 * Only same-origin, path-shaped values are honoured. The redirect target
 * arrives in a form field, which makes it attacker-controlled: without this
 * check the switcher would be an open redirect, and "change language" is
 * exactly the kind of innocuous-looking link someone would click.
 */
export function safeRedirectPath(value: FormDataEntryValue | null): string {
  if (typeof value !== "string") return "/";
  const candidate = value.trim();
  // Must start with a single "/" — "//evil.test" is protocol-relative and
  // leaves the site, and "https://…" obviously does.
  if (!candidate.startsWith("/") || candidate.startsWith("//")) return "/";
  if (candidate.includes("\\") || candidate.includes("\n") || candidate.includes("\r")) return "/";
  return candidate;
}
