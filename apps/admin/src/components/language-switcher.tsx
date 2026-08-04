/**
 * Language picker for the admin shell's top bar.
 *
 * A native `<select>` rather than a custom menu: ninety-nine options with
 * non-Latin scripts is exactly the case where the platform control wins — it
 * gets type-ahead, keyboard navigation, screen-reader announcement and sensible
 * mobile presentation for free, in every one of those scripts.
 *
 * Options are grouped the same way the storefront groups them (Indian
 * languages first, then world languages, each ordered by number of speakers)
 * because a flat list of ninety-nine is a wall of text nobody scans.
 */

import { Globe } from "lucide-react";

import { LOCALES } from "@truegrit/i18n";

import { localeLabel, useLocaleControls, useT } from "../lib/i18n";

const INDIAN_LOCALES = LOCALES.filter((locale) => locale.group === "indian");
const WORLD_LOCALES = LOCALES.filter((locale) => locale.group === "world");

export function LanguageSwitcher() {
  const { locale, setLocale } = useLocaleControls();
  const t = useT();

  return (
    <label className="flex items-center gap-1.5 text-sm text-ink-muted">
      <Globe size={15} aria-hidden />
      <span className="sr-only">{t("Language")}</span>
      <select
        value={locale}
        onChange={(event) => setLocale(event.target.value)}
        className="min-h-8 max-w-[10rem] rounded-sm border border-line bg-surface px-2 text-sm text-ink"
        aria-label={t("Change language")}
      >
        <optgroup label={t("Indian languages")}>
          {INDIAN_LOCALES.map((definition) => (
            <option key={definition.code} value={definition.code}>
              {localeLabel(definition.code)}
            </option>
          ))}
        </optgroup>
        <optgroup label={t("World languages")}>
          {WORLD_LOCALES.map((definition) => (
            <option key={definition.code} value={definition.code}>
              {localeLabel(definition.code)}
            </option>
          ))}
        </optgroup>
      </select>
    </label>
  );
}
