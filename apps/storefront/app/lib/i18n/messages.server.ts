/**
 * Server-only catalogue registry.
 *
 * Every translation is imported here and nowhere else. Because this module is
 * only ever reached from a loader, the bundler keeps every non-English
 * catalogue out of the browser build: a visitor downloads the English source
 * (already in `messages.ts`) plus the entries for the one language they chose.
 *
 * Static imports rather than dynamic ones on purpose. Cloudflare Workers have
 * no filesystem and a cold-start budget measured in milliseconds; dozens of
 * `await import()` calls would trade a few kilobytes of Worker bundle — which
 * costs the visitor nothing — for a round of module resolution on the request
 * path, which costs them latency.
 */

import { DEFAULT_LOCALE } from "./locales";
import type { LocaleMessages } from "./messages";

import as from "./catalog/as";
import ar from "./catalog/ar";
import bn from "./catalog/bn";
import brx from "./catalog/brx";
import de from "./catalog/de";
import doi from "./catalog/doi";
import es from "./catalog/es";
import fa from "./catalog/fa";
import fil from "./catalog/fil";
import fr from "./catalog/fr";
import gu from "./catalog/gu";
import he from "./catalog/he";
import hi from "./catalog/hi";
import id from "./catalog/id";
import it from "./catalog/it";
import ja from "./catalog/ja";
import kn from "./catalog/kn";
import ko from "./catalog/ko";
import kok from "./catalog/kok";
import ks from "./catalog/ks";
import mai from "./catalog/mai";
import ml from "./catalog/ml";
import mni from "./catalog/mni";
import mr from "./catalog/mr";
import ne from "./catalog/ne";
import nl from "./catalog/nl";
import or from "./catalog/or";
import pa from "./catalog/pa";
import pl from "./catalog/pl";
import pt from "./catalog/pt";
import ru from "./catalog/ru";
import sa from "./catalog/sa";
import sat from "./catalog/sat";
import sd from "./catalog/sd";
import sw from "./catalog/sw";
import ta from "./catalog/ta";
import te from "./catalog/te";
import th from "./catalog/th";
import tr from "./catalog/tr";
import uk from "./catalog/uk";
import ur from "./catalog/ur";
import vi from "./catalog/vi";
import zhHans from "./catalog/zh-Hans";
import zhHant from "./catalog/zh-Hant";
import sv from "./catalog/sv";
import nb from "./catalog/nb";
import da from "./catalog/da";
import fi from "./catalog/fi";
import el from "./catalog/el";
import cs from "./catalog/cs";
import hu from "./catalog/hu";
import ro from "./catalog/ro";
import sk from "./catalog/sk";
import bg from "./catalog/bg";

/**
 * Locale code -> that locale's own entries.
 *
 * English is absent by design, not by omission: it is the source, already
 * shipped to the client, and an entry here would send every English visitor a
 * duplicate copy of a catalogue they have.
 */
export const CATALOGUES: Readonly<Record<string, LocaleMessages>> = {
  hi,
  bn,
  mr,
  te,
  ta,
  gu,
  ur,
  kn,
  or,
  ml,
  pa,
  as,
  mai,
  sat,
  ks,
  ne,
  sd,
  kok,
  doi,
  mni,
  brx,
  sa,
  "zh-Hans": zhHans,
  es,
  ar,
  pt,
  fr,
  ru,
  id,
  de,
  ja,
  tr,
  vi,
  ko,
  it,
  fa,
  "zh-Hant": zhHant,
  th,
  pl,
  uk,
  nl,
  fil,
  sw,
  he,
  sv,
  nb,
  da,
  fi,
  el,
  cs,
  hu,
  ro,
  sk,
  bg,
};

/**
 * The entries to send the browser for `locale`.
 *
 * Returns an empty object for English and for anything unrecognised — the
 * provider falls back to the English source either way, so an unknown code
 * degrades to a readable page rather than an error.
 */
export function messagesFor(locale: string): LocaleMessages {
  if (locale === DEFAULT_LOCALE) return {};
  return CATALOGUES[locale] ?? {};
}
