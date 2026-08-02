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
