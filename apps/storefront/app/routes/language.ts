/**
 * The language switch endpoint: sets the preference cookie and sends the
 * visitor back where they were.
 *
 * A resource route with a plain form POST, not a fetch. That makes the switcher
 * work with JavaScript disabled or still loading — which matters here more than
 * almost anywhere else on the site, because someone who cannot read the current
 * language has no way to recover if the control silently does nothing.
 *
 * POST-then-redirect (303) rather than rendering a response, so the language
 * change does not sit in history as a resubmittable form.
 */

import { redirect } from "react-router";

import type { Route } from "./+types/language";
import { LOCALE_QUERY_PARAM, localeCookie, safeRedirectPath } from "../lib/i18n/resolve.server";
import { DEFAULT_LOCALE, getLocale } from "../lib/i18n/locales";

export async function action({ request }: Route.ActionArgs) {
  const form = await request.formData();
  const requested = String(form.get("locale") ?? "");
  // Unknown codes fall back to the default rather than 400: a stale bookmark or
  // a retired locale should land somebody on a readable page, not an error.
  const locale = getLocale(requested)?.code ?? DEFAULT_LOCALE;

  const target = safeRedirectPath(form.get("redirectTo"));
  // Strip any `?lang=` already on the path being returned to. It outranks the
  // cookie in `resolveLocale`, so leaving it would make the switcher appear to
  // do nothing on exactly the pages reached by a language-specific link.
  const url = new URL(target, "https://placeholder.invalid");
  url.searchParams.delete(LOCALE_QUERY_PARAM);
  const cleaned = `${url.pathname}${url.search}${url.hash}`;

  return redirect(cleaned, {
    status: 303,
    headers: { "set-cookie": localeCookie(locale) },
  });
}

/** A direct GET (a crawler, someone pasting the URL) has nothing to do here. */
export async function loader() {
  return redirect("/");
}
