/**
 * The language picker.
 *
 * A `<form>` around a `<select>` and a submit button, posting to `/language`.
 * Deliberately not a fetch-and-reload: with forty-five options the control has
 * to work before hydration, and the visitor most in need of it is by definition
 * the one who cannot read the page they are stuck on.
 *
 * The button is hidden once JavaScript is available (`onChange` submits the
 * form instead), so the common path is one interaction, and the fallback path
 * is still complete.
 */

import { useRef } from "react";
import { useLocation } from "react-router";

import { useLocaleContext } from "../lib/i18n/context";
import { LOCALES, type LocaleGroup } from "../lib/i18n/locales";

const GROUP_ORDER: readonly LocaleGroup[] = ["indian", "world"];

export function LanguageSwitcher({
  /** Footer sits on the dark band and needs light text; the header is on
   *  canvas. One prop rather than two components — the markup is identical. */
  tone = "light",
  className = "",
}: {
  tone?: "light" | "dark";
  className?: string;
}) {
  const { locale, t } = useLocaleContext();
  const location = useLocation();
  const formRef = useRef<HTMLFormElement>(null);

  // Where to send the visitor back to. Rebuilt from the router's own location
  // rather than read from `window`, so it is identical on the server and the
  // client and does not differ across hydration.
  const redirectTo = `${location.pathname}${location.search}`;

  const selectClass =
    tone === "dark"
      ? "min-h-9 rounded-sm border border-white/25 bg-transparent px-2 py-1 text-sm text-ink-inverse focus:border-white focus:outline-none"
      : "min-h-9 rounded-sm border border-line bg-canvas px-2 py-1 text-sm text-ink focus:border-brand focus:outline-none";

  return (
    <form
      ref={formRef}
      method="post"
      action="/language"
      className={`flex items-center gap-2 ${className}`}
    >
      <input type="hidden" name="redirectTo" value={redirectTo} />
      <label htmlFor="language-select" className="sr-only">
        {t("language.change")}
      </label>
      <select
        id="language-select"
        name="locale"
        defaultValue={locale}
        onChange={(event) => event.currentTarget.form?.requestSubmit()}
        className={selectClass}
        // The options are in their own scripts; the control itself is described
        // in the page's language.
        aria-label={t("language.change")}
      >
        {GROUP_ORDER.map((group) => (
          <optgroup
            key={group}
            label={group === "indian" ? t("language.indian") : t("language.world")}
          >
            {LOCALES.filter((entry) => entry.group === group).map((entry) => (
              // `lang` on the option so a screen reader pronounces each name in
              // its own language rather than reading Devanagari as English.
              <option key={entry.code} value={entry.code} lang={entry.code}>
                {entry.nativeName}
                {entry.nativeName === entry.englishName ? "" : ` — ${entry.englishName}`}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {/* Replaced by the onChange handler once JavaScript runs. `noscript`
          cannot wrap interactive content reliably inside React's tree, so the
          button is always rendered and hidden by the same script that makes it
          redundant — see app.css `.js-only-hidden`. */}
      <button
        type="submit"
        className={
          tone === "dark"
            ? "language-switcher-submit min-h-9 rounded-sm border border-white/25 px-3 text-xs text-ink-inverse"
            : "language-switcher-submit min-h-9 rounded-sm border border-line px-3 text-xs text-ink"
        }
      >
        {t("language.apply")}
      </button>
    </form>
  );
}
