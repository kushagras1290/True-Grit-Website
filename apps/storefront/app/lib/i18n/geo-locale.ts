/**
 * Country → default-language guesses, for visitors whose browser gives no
 * useful signal.
 *
 * Country is the first-visit default so language and currency change together:
 * a visitor in Germany receives German and EUR even if the device retained an
 * English factory default. A language the visitor deliberately chooses is
 * stored in a cookie and outranks this mapping; `Accept-Language` remains the
 * fallback only when a request has no valid country signal.
 *
 * This is deliberately a guess, not a claim of nationality or fluency, and it
 * is why `resolveLocale` always pairs a geo-selected locale with a visible way
 * back to English (`LanguageSuggestionPrompt`). The ISO locale dataset covers
 * every country; explicit overrides preserve the strongest national language
 * choices and provide a supported fallback where that language is not shipped.
 */

import countryLocaleMap from "country-locale-map";

import { matchLocale, type LocaleDefinition } from "./locales";

const COUNTRY_LOCALE_OVERRIDES: Readonly<Record<string, string>> = {
  // Europe
  DE: "de",
  AT: "de",
  CH: "de",
  FR: "fr",
  BE: "fr",
  IT: "it",
  ES: "es",
  MX: "es",
  AR: "es",
  CO: "es",
  CL: "es",
  PE: "es",
  PT: "pt",
  BR: "pt",
  NL: "nl",
  PL: "pl",
  RU: "ru",
  UA: "uk",
  TR: "tr",
  SE: "sv",
  NO: "nb",
  DK: "da",
  FI: "fi",
  GR: "el",
  CZ: "cs",
  HU: "hu",
  RO: "ro",
  SK: "sk",
  BG: "bg",
  // Middle East / Africa
  SA: "ar",
  AE: "ar",
  EG: "ar",
  QA: "ar",
  KW: "ar",
  IL: "he",
  IR: "fa",
  KE: "sw",
  TZ: "sw",
  UG: "sw",
  // East / Southeast Asia
  JP: "ja",
  KR: "ko",
  CN: "zh-Hans",
  SG: "zh-Hans",
  TW: "zh-Hant",
  HK: "zh-Hant",
  TH: "th",
  VN: "vi",
  ID: "id",
  PH: "fil",
  // ISO defaults whose primary language is not yet in the storefront.
  BT: "en",
  BV: "nb",
  CV: "pt",
  ER: "en",
  FO: "da",
  GH: "en",
  GL: "da",
  MV: "en",
  PK: "ur",
  WS: "en",
  LK: "en",
  SJ: "nb",
  TO: "en",
  VU: "en",
  ZM: "en",
} as const;

/**
 * The locale a country most plausibly reads, or `null` for an invalid country.
 */
export function matchCountryLocale(country: string | null | undefined): LocaleDefinition | null {
  if (!country) return null;
  const countryCode = country.trim().toUpperCase();
  if (!countryCode) return null;
  const code =
    COUNTRY_LOCALE_OVERRIDES[countryCode] ?? countryLocaleMap.getLocaleByAlpha2(countryCode);
  return code ? matchLocale(code.replaceAll("_", "-")) : null;
}

/**
 * Indian state/UT → locale, a more precise refinement than the country-level
 * Hindi default. State is a real signal a country never was — a Punjab visitor and
 * a Tamil Nadu visitor should not get the same guess just because both are
 * "IN". Keyed by full state name (what Cloudflare's `cf.region` typically
 * carries) in `INDIA_STATE_TO_LOCALE`, and by ISO-3166-2 subdivision code
 * (`cf.regionCode`, e.g. "IN-PB") in `INDIA_REGION_CODE_TO_LOCALE` — whichever
 * the edge actually populates, see `resolveRegion` (geo.server.ts).
 *
 * Where a state does not have a matching language in the shipped catalogue,
 * use English (an official language there) instead of incorrectly assuming
 * Hindi. This keeps every Indian subdivision deterministic without claiming a
 * language the storefront cannot actually render.
 */
const INDIA_STATE_TO_LOCALE: Readonly<Record<string, string>> = {
  "ANDHRA PRADESH": "te",
  "ARUNACHAL PRADESH": "en",
  ASSAM: "as",
  BIHAR: "hi",
  CHHATTISGARH: "hi",
  GOA: "kok",
  GUJARAT: "gu",
  HARYANA: "hi",
  "HIMACHAL PRADESH": "hi",
  JHARKHAND: "hi",
  "JAMMU AND KASHMIR": "ks",
  KARNATAKA: "kn",
  KERALA: "ml",
  "MADHYA PRADESH": "hi",
  MAHARASHTRA: "mr",
  MANIPUR: "mni",
  MEGHALAYA: "en",
  MIZORAM: "en",
  NAGALAND: "en",
  ODISHA: "or",
  ORISSA: "or",
  PUNJAB: "pa",
  RAJASTHAN: "hi",
  SIKKIM: "ne",
  "TAMIL NADU": "ta",
  TELANGANA: "te",
  TRIPURA: "bn",
  "UTTAR PRADESH": "hi",
  UTTARAKHAND: "hi",
  "WEST BENGAL": "bn",
  // Union territories.
  "ANDAMAN AND NICOBAR ISLANDS": "hi",
  CHANDIGARH: "hi",
  "DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "gu",
  DELHI: "hi",
  "NCT OF DELHI": "hi",
  LADAKH: "hi",
  LAKSHADWEEP: "ml",
  PUDUCHERRY: "ta",
} as const;

const INDIA_REGION_CODE_TO_LOCALE: Readonly<Record<string, string>> = {
  AP: "te",
  AR: "en",
  AS: "as",
  BR: "hi",
  CG: "hi",
  CT: "hi",
  GA: "kok",
  GJ: "gu",
  HR: "hi",
  HP: "hi",
  JH: "hi",
  JK: "ks",
  KA: "kn",
  KL: "ml",
  MP: "hi",
  MH: "mr",
  MN: "mni",
  ML: "en",
  MZ: "en",
  NL: "en",
  OR: "or",
  PB: "pa",
  RJ: "hi",
  SK: "ne",
  TN: "ta",
  TG: "te",
  TR: "bn",
  UP: "hi",
  UK: "hi",
  UT: "hi",
  WB: "bn",
  AN: "hi",
  CH: "hi",
  DH: "gu",
  DD: "gu",
  DL: "hi",
  LA: "hi",
  LD: "ml",
  PY: "ta",
} as const;

/**
 * The locale an Indian state/UT most plausibly reads, from whichever of
 * `region` (full name) or `regionCode` (ISO-3166-2, with or without the
 * "IN-" prefix) Cloudflare populated. `null` when neither is present or
 * neither matches a mapped state — the caller falls back to
 * `matchCountryLocale`/`Accept-Language` exactly as it would have without
 * this refinement.
 */
export function matchIndiaRegionLocale(
  region: string | null | undefined,
  regionCode: string | null | undefined,
): LocaleDefinition | null {
  const byName = region ? INDIA_STATE_TO_LOCALE[region.trim().toUpperCase()] : undefined;
  if (byName) return matchLocale(byName);

  const normalizedCode = regionCode?.trim().toUpperCase().replace(/^IN-/, "");
  const byCode = normalizedCode ? INDIA_REGION_CODE_TO_LOCALE[normalizedCode] : undefined;
  return byCode ? matchLocale(byCode) : null;
}
