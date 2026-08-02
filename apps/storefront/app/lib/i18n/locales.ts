/**
 * The languages the storefront offers, and how to resolve one.
 *
 * Client-safe and deliberately tiny: this module carries only metadata, never
 * translations. The catalogues themselves are server-only (see
 * `messages.server.ts`) so a visitor downloads one language, not fifty-five.
 *
 * Every entry is keyed by a BCP 47 tag, which is what `<html lang>`,
 * `Accept-Language`, `Intl.*` and hreflang all speak. Chinese is split into
 * `zh-Hans`/`zh-Hant` rather than a bare `zh` because the two scripts are not
 * mutually readable, and a reader of one is not served by the other.
 */

export type TextDirection = "ltr" | "rtl";

/** Broad groupings, used only to keep the language menu navigable — a flat
 *  list of fifty-five is a wall of text nobody scans. */
export type LocaleGroup = "indian" | "world";

export interface LocaleDefinition {
  /** BCP 47 tag. Also the cookie value and the `?lang=` parameter. */
  code: string;
  /** The name in the language itself — what someone looking for their own
   *  language actually scans for. Always shown. */
  nativeName: string;
  /** The English name, shown as a subtitle so an operator (or a visitor who
   *  landed in a language they cannot read) can still navigate. */
  englishName: string;
  dir: TextDirection;
  group: LocaleGroup;
}

/** The site's source language. Every catalogue is authored against it, and it
 *  is the fallback for any key a translation has not filled in yet. */
export const DEFAULT_LOCALE = "en";

/**
 * Indian languages first — the store is India-first in currency, payment and
 * delivery, so its languages lead. Within each group, ordered by number of
 * speakers rather than alphabetically: the menu should put the likely answer
 * near the top.
 *
 * The 22 languages of the Eighth Schedule to the Constitution of India are all
 * present, plus English.
 */
export const LOCALES: readonly LocaleDefinition[] = [
  { code: "en", nativeName: "English", englishName: "English", dir: "ltr", group: "indian" },
  { code: "hi", nativeName: "हिन्दी", englishName: "Hindi", dir: "ltr", group: "indian" },
  { code: "bn", nativeName: "বাংলা", englishName: "Bengali", dir: "ltr", group: "indian" },
  { code: "mr", nativeName: "मराठी", englishName: "Marathi", dir: "ltr", group: "indian" },
  { code: "te", nativeName: "తెలుగు", englishName: "Telugu", dir: "ltr", group: "indian" },
  { code: "ta", nativeName: "தமிழ்", englishName: "Tamil", dir: "ltr", group: "indian" },
  { code: "gu", nativeName: "ગુજરાતી", englishName: "Gujarati", dir: "ltr", group: "indian" },
  { code: "ur", nativeName: "اردو", englishName: "Urdu", dir: "rtl", group: "indian" },
  { code: "kn", nativeName: "ಕನ್ನಡ", englishName: "Kannada", dir: "ltr", group: "indian" },
  { code: "or", nativeName: "ଓଡ଼ିଆ", englishName: "Odia", dir: "ltr", group: "indian" },
  { code: "ml", nativeName: "മലയാളം", englishName: "Malayalam", dir: "ltr", group: "indian" },
  { code: "pa", nativeName: "ਪੰਜਾਬੀ", englishName: "Punjabi", dir: "ltr", group: "indian" },
  { code: "as", nativeName: "অসমীয়া", englishName: "Assamese", dir: "ltr", group: "indian" },
  { code: "mai", nativeName: "मैथिली", englishName: "Maithili", dir: "ltr", group: "indian" },
  { code: "sat", nativeName: "ᱥᱟᱱᱛᱟᱲᱤ", englishName: "Santali", dir: "ltr", group: "indian" },
  { code: "ks", nativeName: "کٲشُر", englishName: "Kashmiri", dir: "rtl", group: "indian" },
  { code: "ne", nativeName: "नेपाली", englishName: "Nepali", dir: "ltr", group: "indian" },
  { code: "sd", nativeName: "سنڌي", englishName: "Sindhi", dir: "rtl", group: "indian" },
  { code: "kok", nativeName: "कोंकणी", englishName: "Konkani", dir: "ltr", group: "indian" },
  { code: "doi", nativeName: "डोगरी", englishName: "Dogri", dir: "ltr", group: "indian" },
  { code: "mni", nativeName: "ꯃꯤꯇꯩꯂꯣꯟ", englishName: "Manipuri", dir: "ltr", group: "indian" },
  { code: "brx", nativeName: "बर’", englishName: "Bodo", dir: "ltr", group: "indian" },
  { code: "sa", nativeName: "संस्कृतम्", englishName: "Sanskrit", dir: "ltr", group: "indian" },

  {
    code: "zh-Hans",
    nativeName: "简体中文",
    englishName: "Chinese (Simplified)",
    dir: "ltr",
    group: "world",
  },
  { code: "es", nativeName: "Español", englishName: "Spanish", dir: "ltr", group: "world" },
  { code: "ar", nativeName: "العربية", englishName: "Arabic", dir: "rtl", group: "world" },
  { code: "pt", nativeName: "Português", englishName: "Portuguese", dir: "ltr", group: "world" },
  { code: "fr", nativeName: "Français", englishName: "French", dir: "ltr", group: "world" },
  { code: "ru", nativeName: "Русский", englishName: "Russian", dir: "ltr", group: "world" },
  {
    code: "id",
    nativeName: "Bahasa Indonesia",
    englishName: "Indonesian",
    dir: "ltr",
    group: "world",
  },
  { code: "de", nativeName: "Deutsch", englishName: "German", dir: "ltr", group: "world" },
  { code: "ja", nativeName: "日本語", englishName: "Japanese", dir: "ltr", group: "world" },
  { code: "tr", nativeName: "Türkçe", englishName: "Turkish", dir: "ltr", group: "world" },
  { code: "vi", nativeName: "Tiếng Việt", englishName: "Vietnamese", dir: "ltr", group: "world" },
  { code: "ko", nativeName: "한국어", englishName: "Korean", dir: "ltr", group: "world" },
  { code: "it", nativeName: "Italiano", englishName: "Italian", dir: "ltr", group: "world" },
  { code: "fa", nativeName: "فارسی", englishName: "Persian", dir: "rtl", group: "world" },
  {
    code: "zh-Hant",
    nativeName: "繁體中文",
    englishName: "Chinese (Traditional)",
    dir: "ltr",
    group: "world",
  },
  { code: "th", nativeName: "ไทย", englishName: "Thai", dir: "ltr", group: "world" },
  { code: "pl", nativeName: "Polski", englishName: "Polish", dir: "ltr", group: "world" },
  { code: "uk", nativeName: "Українська", englishName: "Ukrainian", dir: "ltr", group: "world" },
  { code: "nl", nativeName: "Nederlands", englishName: "Dutch", dir: "ltr", group: "world" },
  { code: "fil", nativeName: "Filipino", englishName: "Filipino", dir: "ltr", group: "world" },
  { code: "sw", nativeName: "Kiswahili", englishName: "Swahili", dir: "ltr", group: "world" },
  { code: "he", nativeName: "עברית", englishName: "Hebrew", dir: "rtl", group: "world" },
  { code: "sv", nativeName: "Svenska", englishName: "Swedish", dir: "ltr", group: "world" },
  { code: "nb", nativeName: "Norsk bokmål", englishName: "Norwegian", dir: "ltr", group: "world" },
  { code: "da", nativeName: "Dansk", englishName: "Danish", dir: "ltr", group: "world" },
  { code: "fi", nativeName: "Suomi", englishName: "Finnish", dir: "ltr", group: "world" },
  { code: "el", nativeName: "Ελληνικά", englishName: "Greek", dir: "ltr", group: "world" },
  { code: "cs", nativeName: "Čeština", englishName: "Czech", dir: "ltr", group: "world" },
  { code: "hu", nativeName: "Magyar", englishName: "Hungarian", dir: "ltr", group: "world" },
  { code: "ro", nativeName: "Română", englishName: "Romanian", dir: "ltr", group: "world" },
  { code: "sk", nativeName: "Slovenčina", englishName: "Slovak", dir: "ltr", group: "world" },
  { code: "bg", nativeName: "Български", englishName: "Bulgarian", dir: "ltr", group: "world" },
] as const;

const BY_CODE: ReadonlyMap<string, LocaleDefinition> = new Map(
  LOCALES.map((locale) => [locale.code.toLowerCase(), locale]),
);

/** Base tag ("zh" -> "zh-Hans") for requests that name a language but not a
 *  script. First match wins, which is why `zh-Hans` precedes `zh-Hant` above. */
const BY_BASE_LANGUAGE: ReadonlyMap<string, LocaleDefinition> = new Map(
  [...LOCALES]
    .reverse()
    .map((locale) => [locale.code.split("-")[0]!.toLowerCase(), locale] as const),
);

export function isSupportedLocale(code: string): boolean {
  return BY_CODE.has(code.trim().toLowerCase());
}

export function getLocale(code: string): LocaleDefinition | null {
  return BY_CODE.get(code.trim().toLowerCase()) ?? null;
}

/**
 * The closest supported locale to `code`, or null.
 *
 * Falls back from the full tag to the base language, so `pt-BR` finds
 * Portuguese and `en-GB` finds English rather than dropping to the default.
 * Region subtags are deliberately not modelled: we translate languages, not
 * regional variants, and pretending otherwise would multiply the catalogues
 * without adding a single new word.
 */
export function matchLocale(code: string | null | undefined): LocaleDefinition | null {
  if (!code) return null;
  const normalized = code.trim().toLowerCase();
  if (!normalized) return null;
  const exact = BY_CODE.get(normalized);
  if (exact) return exact;
  const base = normalized.split("-")[0]!;
  return BY_BASE_LANGUAGE.get(base) ?? null;
}

/**
 * Best supported locale for an `Accept-Language` header.
 *
 * Parses q-values properly rather than taking the first tag: browsers do send
 * ordered lists with weights, and honouring them is the difference between a
 * Hindi speaker whose browser prefers Hindi getting Hindi, and getting whatever
 * their OS happened to list first.
 *
 * Never throws — a malformed header from a crawler must not 500 the homepage.
 */
export function matchAcceptLanguage(header: string | null | undefined): LocaleDefinition | null {
  if (!header) return null;
  const candidates = header
    .split(",")
    .map((part) => {
      const [tag, ...parameters] = part.trim().split(";");
      if (!tag) return null;
      const qParameter = parameters.find((parameter) => parameter.trim().startsWith("q="));
      const quality = qParameter ? Number.parseFloat(qParameter.trim().slice(2)) : 1;
      return { tag: tag.trim(), quality: Number.isFinite(quality) ? quality : 0 };
    })
    .filter(
      (entry): entry is { tag: string; quality: number } => entry !== null && entry.quality > 0,
    )
    .sort((a, b) => b.quality - a.quality);

  for (const candidate of candidates) {
    // "*" means "anything"; that is what the default locale is for.
    if (candidate.tag === "*") return null;
    const matched = matchLocale(candidate.tag);
    if (matched) return matched;
  }
  return null;
}

export function localeDirection(code: string): TextDirection {
  return getLocale(code)?.dir ?? "ltr";
}

/** The cookie the visitor's choice is remembered in. Read on the server so the
 *  very first paint is already translated — a client-side switch would flash
 *  English first, which is exactly the experience this feature exists to fix. */
export const LOCALE_COOKIE_NAME = "truegrit_lang";

/** A year. The choice is a preference, not a session: someone who picks Tamil
 *  should still get Tamil next month. */
export const LOCALE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;
