/**
 * The storefront's view of the shared language list.
 *
 * The definitions themselves live in `@truegrit/i18n` so the storefront and the
 * admin panel cannot drift into advertising different languages. This module
 * stays as the storefront's import path — dozens of files and two build scripts
 * reference it — and adds the one constant that is storefront-only: the cookie
 * the visitor's choice is remembered in.
 */

export {
  DEFAULT_LOCALE,
  LOCALES,
  getLocale,
  isSupportedLocale,
  localeDirection,
  matchAcceptLanguage,
  matchLocale,
  type LocaleDefinition,
  type LocaleGroup,
  type TextDirection,
} from "@truegrit/i18n";

/** The cookie the visitor's choice is remembered in. Read on the server so the
 *  very first paint is already translated — a client-side switch would flash
 *  English first, which is exactly the experience this feature exists to fix. */
export const LOCALE_COOKIE_NAME = "truegrit_lang";

/** A year. The choice is a preference, not a session: someone who picks Tamil
 *  should still get Tamil next month. */
export const LOCALE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;
