/**
 * Locale context for the storefront.
 *
 * The root loader resolves the locale on the server and hands down only that
 * locale's *own* entries (`messages.server.ts`). This provider merges them over
 * the English source, which is already in the bundle, so:
 *
 *   * the client payload carries one language, not forty-five;
 *   * English requests carry nothing at all;
 *   * and `t()` can never return undefined, whatever the catalogue is missing.
 *
 * The merge is done once per locale change, not per render — a page with a
 * hundred labels would otherwise rebuild the dictionary a hundred times.
 */

import { createContext, useContext, useMemo, type ReactNode } from "react";

import { DEFAULT_LOCALE, localeDirection, type TextDirection } from "./locales";
import {
  EN_MESSAGES,
  translate,
  type LocaleMessages,
  type MessageKey,
  type ResolvedMessages,
} from "./messages";

export interface LocaleContextValue {
  locale: string;
  dir: TextDirection;
  messages: ResolvedMessages;
  /** Look up a string, substituting `{placeholder}` values. */
  t: (key: MessageKey, values?: Readonly<Record<string, string | number>>) => string;
}

const FALLBACK: LocaleContextValue = {
  locale: DEFAULT_LOCALE,
  dir: "ltr",
  messages: EN_MESSAGES,
  t: (key, values) => translate(EN_MESSAGES, key, values),
};

const LocaleContext = createContext<LocaleContextValue>(FALLBACK);

export function LocaleProvider({
  locale,
  messages,
  children,
}: {
  locale: string;
  /** The locale's own entries. English fills the gaps here, not upstream. */
  messages: LocaleMessages;
  children: ReactNode;
}) {
  const value = useMemo<LocaleContextValue>(() => {
    const resolved: ResolvedMessages = { ...EN_MESSAGES, ...stripBlanks(messages) };
    return {
      locale,
      dir: localeDirection(locale),
      messages: resolved,
      t: (key, values) => translate(resolved, key, values),
    };
  }, [locale, messages]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

/**
 * Drop empty and whitespace-only entries before they can shadow English.
 *
 * A blank string is a *plausible* translation-file mistake and an
 * *implausible* intention: nobody means for a button to have no label. Treating
 * it as "not translated" turns a silent broken control into an untranslated
 * one.
 */
function stripBlanks(messages: LocaleMessages): LocaleMessages {
  const entries = Object.entries(messages).filter(
    ([, value]) => typeof value === "string" && value.trim() !== "",
  );
  return Object.fromEntries(entries) as LocaleMessages;
}

/** The full locale context: code, direction and the resolved catalogue. */
export function useLocaleContext(): LocaleContextValue {
  return useContext(LocaleContext);
}

/**
 * The translate function on its own — the common case.
 *
 * ```tsx
 * const t = useTranslate();
 * <button>{t("partner.submit")}</button>
 * ```
 */
export function useTranslate(): LocaleContextValue["t"] {
  return useContext(LocaleContext).t;
}
