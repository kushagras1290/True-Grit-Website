/**
 * Country → default-language guesses, for visitors whose browser gives no
 * useful signal.
 *
 * `Accept-Language` is the better source when it names a real language — it is
 * what the visitor actually configured. But a large share of browsers are left
 * on a device-wide "English" default regardless of who is using them or where,
 * which makes a bare `en` from that header ambiguous: is it a genuine
 * preference, or just what the OS shipped with? Country, from Cloudflare's
 * edge (`resolveCountry`), disambiguates that case — see the priority order in
 * `resolveLocale`.
 *
 * This is deliberately a guess, not a claim of nationality or fluency, and it
 * is why `resolveLocale` always pairs a geo-selected locale with a visible way
 * back to English (`LanguageSuggestionPrompt`). Only the country's clearly
 * dominant official/majority language is listed; a country with no single
 * obvious answer (the U.S., Canada, most of India) is left out on purpose
 * rather than guessed at.
 *
 * India is absent for the same reason the accept-language step already ranks
 * above this one: the storefront is India-first across 22 languages with no
 * single "the" language, so guessing one from country alone would be wrong far
 * more often than it would help.
 */

import { matchLocale, type LocaleDefinition } from "./locales";

const COUNTRY_TO_LOCALE: Readonly<Record<string, string>> = {
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
} as const;

/**
 * The locale a country most plausibly reads, or `null` when the country is
 * unmapped or the mapped language was never shipped with a catalogue.
 */
export function matchCountryLocale(country: string | null | undefined): LocaleDefinition | null {
  if (!country) return null;
  const code = COUNTRY_TO_LOCALE[country.trim().toUpperCase()];
  return code ? matchLocale(code) : null;
}

/**
 * Indian state/UT → locale, the refinement `COUNTRY_TO_LOCALE` above
 * explicitly declines to make at the country level (see this file's header
 * comment: India has no single dominant language, so guessing wrong would be
 * common). State is a real signal a country never was — a Punjab visitor and
 * a Tamil Nadu visitor should not get the same guess just because both are
 * "IN". Keyed by full state name (what Cloudflare's `cf.region` typically
 * carries) in `INDIA_STATE_TO_LOCALE`, and by ISO-3166-2 subdivision code
 * (`cf.regionCode`, e.g. "IN-PB") in `INDIA_REGION_CODE_TO_LOCALE` — whichever
 * the edge actually populates, see `resolveRegion` (geo.server.ts).
 *
 * A state left out on purpose (Nagaland, Mizoram, Meghalaya) has no clearly
 * dominant language among the 22 this storefront ships — the same "leave it
 * out rather than guess wrong" rule `COUNTRY_TO_LOCALE` already applies to
 * India as a whole. Those visitors still get the country-level fallback (or
 * `Accept-Language`), never a forced wrong guess.
 */
const INDIA_STATE_TO_LOCALE: Readonly<Record<string, string>> = {
  "ANDHRA PRADESH": "te",
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
  AS: "as",
  BR: "hi",
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
