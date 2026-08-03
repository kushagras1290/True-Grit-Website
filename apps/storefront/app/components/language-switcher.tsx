/**
 * The language picker.
 *
 * A `<form>` around a `<select>` and a submit button, posting to `/language`.
 * Deliberately not a fetch-and-reload: with one hundred options the control has
 * to work before hydration, and the visitor most in need of it is by definition
 * the one who cannot read the page they are stuck on.
 *
 * The button is hidden once JavaScript is available (`onChange` submits the
 * form instead), so the common path is one interaction, and the fallback path
 * is still complete.
 *
 * `<option>`/`<optgroup>` colours are set explicitly rather than left to
 * inherit `tone`. The open list box is rendered by the OS, not the page, and
 * on Windows/Chromium it inherits the `<select>`'s own `color` for unselected
 * rows while the popup's background stays the system's light default — so the
 * footer's light-on-dark styling (meant for the closed control) leaked into
 * the open list as pale text on a near-white background, unreadable. Locking
 * every option to dark-on-light regardless of `tone` is the fix, and it is
 * correct either way: the popup is never actually dark chrome, whatever the
 * closed control looks like.
 */

import { Globe } from "lucide-react";
import { useRef } from "react";
import { useLocation } from "react-router";

import { useLocaleContext } from "../lib/i18n/context";
import { LOCALES, type LocaleGroup } from "../lib/i18n/locales";
import type { MessageKey } from "../lib/i18n/messages";

const GROUP_ORDER: readonly LocaleGroup[] = ["indian", "world"];

/** Always readable regardless of `tone`, because the open list is native OS
 *  chrome, never the page's own dark/light surface — see the module comment. */
const OPTION_STYLE = { color: "var(--color-ink)", backgroundColor: "var(--color-surface)" };
const OPTGROUP_STYLE = {
  color: "var(--color-ink-muted)",
  backgroundColor: "var(--color-surface)",
  fontWeight: 600,
};

function LocaleOptions({ t }: { t: (key: MessageKey) => string }) {
  return (
    <>
      {GROUP_ORDER.map((group) => (
        <optgroup
          key={group}
          label={group === "indian" ? t("language.indian") : t("language.world")}
          style={OPTGROUP_STYLE}
        >
          {LOCALES.filter((entry) => entry.group === group).map((entry) => (
            // `lang` on the option so a screen reader pronounces each name in
            // its own language rather than reading Devanagari as English.
            <option key={entry.code} value={entry.code} lang={entry.code} style={OPTION_STYLE}>
              {entry.nativeName}
              {entry.nativeName === entry.englishName ? "" : ` — ${entry.englishName}`}
            </option>
          ))}
        </optgroup>
      ))}
    </>
  );
}

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

  // Where to send the visitor back to. Rebuilt from the router's own location
  // rather than read from `window`, so it is identical on the server and the
  // client and does not differ across hydration.
  const redirectTo = `${location.pathname}${location.search}`;

  const selectClass =
    tone === "dark"
      ? "min-h-9 rounded-sm border border-white/25 bg-transparent px-2 py-1 text-sm text-ink-inverse focus:border-white focus:outline-none"
      : "min-h-9 rounded-sm border border-line bg-canvas px-2 py-1 text-sm text-ink focus:border-brand focus:outline-none";

  return (
    <form method="post" action="/language" className={`flex items-center gap-2 ${className}`}>
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
        <LocaleOptions t={t} />
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

/**
 * A compact, icon-only trigger for the header: a globe, and nothing else in
 * the closed state — the header is not the language control's "permanent
 * home" (the footer is, see `chrome.tsx`), so it does not need to announce the
 * current language, only offer a fast way to change it.
 *
 * Same accessible `<select>`-in-a-`<form>` underneath as the full switcher, so
 * it works identically without JavaScript: the icon and the native control
 * occupy the same box, with the `<select>` transparent on top, which is what
 * makes clicking the icon open the real picker rather than a fake one this
 * component would have to keep in sync.
 */
export function HeaderLanguageSwitcher({ className = "" }: { className?: string }) {
  const { locale, t } = useLocaleContext();
  const location = useLocation();
  const formRef = useRef<HTMLFormElement>(null);
  const redirectTo = `${location.pathname}${location.search}`;

  return (
    <form
      ref={formRef}
      method="post"
      action="/language"
      className={`relative inline-flex ${className}`}
    >
      <input type="hidden" name="redirectTo" value={redirectTo} />
      <span
        aria-hidden
        className="pointer-events-none flex min-h-11 min-w-11 items-center justify-center text-ink"
      >
        <Globe size={19} />
      </span>
      <label htmlFor="language-select-icon" className="sr-only">
        {t("language.change")}
      </label>
      <select
        id="language-select-icon"
        name="locale"
        defaultValue={locale}
        onChange={(event) => event.currentTarget.form?.requestSubmit()}
        aria-label={t("language.change")}
        // Invisible and stacked exactly over the globe icon: the click target
        // is real, native `<select>` behaviour (including on touch), the icon
        // is purely decorative labelling for it.
        className="absolute inset-0 h-full w-full cursor-pointer appearance-none opacity-0"
      >
        <LocaleOptions t={t} />
      </select>
      {/* No visible fallback button here on purpose: this control is a
          convenience duplicate of the fully accessible switcher that is always
          present in the footer and the mobile menu (see chrome.tsx), so a
          visitor without JavaScript loses nothing by this one instance not
          auto-submitting — they still have the primary control. `sr-only`
          rather than removed, so it stays reachable by keyboard/screen reader
          even though sighted mouse users route through the select above. */}
      <button type="submit" className="sr-only">
        {t("language.apply")}
      </button>
    </form>
  );
}
