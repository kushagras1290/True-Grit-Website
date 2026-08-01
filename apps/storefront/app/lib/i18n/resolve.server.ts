/**
 * Server-side locale resolution and the cookie that remembers it.
 *
 * Resolved in the root loader so the very first byte of HTML is already in the
 * right language. A client-side switch would paint English, hydrate, then
 * repaint — the exact flash this feature exists to remove — and would leave
 * crawlers, which do not run JavaScript, seeing only English.
 */

import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE_MAX_AGE_SECONDS,
  LOCALE_COOKIE_NAME,
  getLocale,
  matchAcceptLanguage,
  matchLocale,
  type LocaleDefinition,
} from "./locales";

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

/**
 * Which language to render, in priority order:
 *
 *   1. `?lang=` — an explicit link, and the switcher's no-JavaScript path.
 *   2. The cookie — what this visitor chose last time.
 *   3. `Accept-Language` — what their browser says, q-values honoured.
 *   4. English.
 *
 * The browser is consulted *after* the cookie, never before: an explicit choice
 * has to survive a browser whose language list says otherwise, which is the
 * common case for a Tamil speaker on an English-configured phone.
 */
export function resolveLocale(request: Request): LocaleDefinition {
  const url = new URL(request.url);
  const fromQuery = matchLocale(url.searchParams.get(LOCALE_QUERY_PARAM));
  if (fromQuery) return fromQuery;

  const fromCookie = matchLocale(readCookie(request.headers.get("cookie"), LOCALE_COOKIE_NAME));
  if (fromCookie) return fromCookie;

  const fromHeader = matchAcceptLanguage(request.headers.get("accept-language"));
  if (fromHeader) return fromHeader;

  // Non-null: DEFAULT_LOCALE is always a registered locale.
  return getLocale(DEFAULT_LOCALE)!;
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
export function localeCookie(locale: string): string {
  const safe = getLocale(locale)?.code ?? DEFAULT_LOCALE;
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
