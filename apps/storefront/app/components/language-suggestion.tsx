/**
 * "We picked this language for you" — the escape hatch for a locale chosen by
 * guesswork rather than something the visitor stated.
 *
 * Only ever shown when the root loader resolved the page's language from the
 * visitor's country (`localeSource === "geo"`, see `resolve.server.ts`). A
 * locale from a cookie, a `?lang=` link, or the browser's own
 * `Accept-Language` header is something the visitor already told us — this
 * prompt would be noise there. A geo guess is different: it is still just a
 * guess, and the one thing it must never do is strand a visitor in a language
 * they cannot read with no visible way out.
 *
 * Rendered as a popover under the header's globe button on screens wide
 * enough to show it (`sm:` and up, matching `HeaderLanguageSwitcher`'s own
 * `hidden sm:inline-flex`) — the little pointer at its top-right reads as
 * having come FROM that button, which is what actually makes "you can change
 * this" legible at a glance instead of a stray toast the visitor has to
 * connect to the control themselves. Below `sm`, where that button is not in
 * the header at all (it lives in the mobile menu/footer instead), it falls
 * back to a plain bottom-of-screen card with no button to point at.
 *
 * Deliberately in English, always, regardless of which language it is
 * offering an escape from — the entire point is to be legible to someone who
 * may not read the language the page just switched to. This is the one piece
 * of storefront chrome that intentionally sits outside the `t()` catalogue
 * system rather than needing a translation in all fifty-five languages: a
 * translated version of "switch to English" would defeat its own purpose for
 * exactly the visitor who most needs it.
 */

import { Globe } from "lucide-react";
import { useEffect, useState } from "react";

import { getLocale } from "../lib/i18n/locales";

const DISMISS_COOKIE = "tg_lang_prompt_seen";
// A season, not forever: a guess an owner or visitor never acted on should be
// offered again eventually rather than silently suppressed for years, in case
// the geo signal (or the visitor's actual location) later changes.
const DISMISS_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 120;

function hasSeenPrompt(): boolean {
  return typeof document !== "undefined" && document.cookie.includes(`${DISMISS_COOKIE}=1`);
}

function markSeen(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${DISMISS_COOKIE}=1; Path=/; Max-Age=${DISMISS_COOKIE_MAX_AGE_SECONDS}; SameSite=Lax`;
}

export function LanguageSuggestionPrompt({
  locale,
  active,
}: {
  /** The BCP 47 code the page actually rendered in. */
  locale: string;
  /** Whether the root loader's resolution came from geo — every other
   *  condition (already seen, already English) is checked inside. */
  active: boolean;
}) {
  // Mount-gated: the dismissal cookie is only ever readable in the browser,
  // and checking it in the initial render would make the server and client
  // markup disagree (a hydration mismatch) for a visitor who dismissed it on
  // a previous visit. Starting closed and opening after mount costs one
  // frame, which is a fair price for never fighting the visitor's own
  // dismissal on the very next repaint.
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (active && locale !== "en" && !hasSeenPrompt()) setOpen(true);
  }, [active, locale]);

  if (!open) return null;
  const definition = getLocale(locale);
  const languageName = definition?.nativeName ?? locale;

  function dismiss() {
    markSeen();
    setOpen(false);
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="animate-language-prompt-in fixed inset-x-4 bottom-4 z-50 mx-auto max-w-sm sm:inset-x-auto sm:top-16 sm:right-4 sm:bottom-auto sm:left-auto sm:mx-0 sm:w-80 md:right-6"
    >
      {/* The pointer: a small rotated square clipped by the card's own
          overflow, positioned to read as this popover having dropped down
          FROM the header's globe button rather than appearing out of
          nowhere. Only drawn on `sm:` and up, alongside the top-anchored
          placement it belongs to -- the mobile card below has no header
          button in view to point at. */}
      <div
        aria-hidden
        className="absolute -top-1.5 right-6 hidden h-3 w-3 rotate-45 border-t border-l border-line bg-surface sm:block"
      />
      <div className="relative overflow-hidden rounded-lg border border-line bg-surface shadow-overlay">
        <div className="flex items-start gap-3 p-4">
          <span
            aria-hidden
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand/10 text-brand"
          >
            <Globe size={18} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium text-ink">We set your language to {languageName}</p>
              <button
                type="button"
                aria-label="Dismiss"
                className="-mt-1 -mr-1 shrink-0 rounded-sm p-1 text-ink-muted hover:text-ink"
                onClick={dismiss}
              >
                ×
              </button>
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              Based on your region — you can change it any time from the language button above.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                className="min-h-9 rounded-sm bg-brand px-3 text-xs font-medium text-ink-inverse hover:opacity-90"
                onClick={dismiss}
              >
                Keep {languageName}
              </button>
              {/* A real form post, like the switcher itself — this still has to
                  work if the visitor has JavaScript but the click handler above
                  somehow does not fire, and it is the one action here with a
                  server-side effect (setting the locale cookie), so it earns
                  the heavier mechanism the "Keep" button does not need. */}
              <form method="post" action="/language" className="inline-flex">
                <input type="hidden" name="locale" value="en" />
                <input
                  type="hidden"
                  name="redirectTo"
                  value={
                    typeof window !== "undefined"
                      ? `${window.location.pathname}${window.location.search}`
                      : "/"
                  }
                />
                <button
                  type="submit"
                  className="min-h-9 rounded-sm border border-line px-3 text-xs font-medium text-ink hover:bg-subtle"
                  onClick={markSeen}
                >
                  Switch to English
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
