/**
 * The catalogue-agnostic half of the translation system.
 *
 * Both apps translate by *English source text* rather than by symbolic keys:
 * a component hands over the words it would otherwise render, and gets back the
 * same words in the active language. Anything with no catalogue entry — a
 * product name, a customer's comment, an API error — falls through unchanged,
 * which is what makes it safe to apply these helpers indiscriminately.
 *
 * `createLocaleRuntime` binds that machinery to one app's English catalogue and
 * returns the provider and hooks that app should use. Keeping the catalogue out
 * of this module is the point: the storefront and the admin panel share the
 * mechanism and the language list, and share none of their words.
 */

import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";

import { DEFAULT_LOCALE, localeDirection, type TextDirection } from "./locales";

export type FormatValues = Readonly<Record<string, string | number>>;

/** A catalogue: English source text -> the same text in one language. */
export type Catalogue = Readonly<Record<string, string>>;

export interface LocaleContextValue {
  locale: string;
  dir: TextDirection;
  /** Translate one English source string. */
  t: (source: string) => string;
  /** Translate, then substitute `{placeholder}` values. */
  format: (source: string, values: FormatValues) => string;
}

/**
 * Substitute `{placeholder}` values into an already-translated template.
 *
 * Unsupplied placeholders are preserved verbatim: a visible `{count}` is a bug
 * somebody can see and report, whereas silently emptying it hides one.
 */
export function interpolate(template: string, values: FormatValues): string {
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match,
  );
}

/**
 * Drop blank entries before they can shadow English.
 *
 * An empty string is a plausible translation-file mistake and an implausible
 * intention — nobody means for a button to have no label — so treating it as
 * "not translated" turns a silently broken control into a merely untranslated
 * one.
 */
function withoutBlanks(catalogue: Catalogue): Catalogue {
  return Object.fromEntries(
    Object.entries(catalogue).filter(([, value]) => typeof value === "string" && value.trim()),
  );
}

export interface LocaleRuntime {
  LocaleProvider: (props: {
    locale: string;
    /** The active language's entries, keyed by English source text. */
    catalogue?: Catalogue;
    children: ReactNode;
  }) => ReactNode;
  useLocale: () => LocaleContextValue;
  /** Translate literal JSX copy: `<T>Save</T>`. */
  T: (props: { children: ReactNode }) => ReactNode;
  /** Translate string props: `placeholder={t("Search")}`. */
  useT: () => (source: string) => string;
  /** Translate interpolated copy: `format("{count} items", { count })`. */
  useFormat: () => (source: string, values: FormatValues) => string;
}

export function createLocaleRuntime(): LocaleRuntime {
  const fallback: LocaleContextValue = {
    locale: DEFAULT_LOCALE,
    dir: "ltr",
    t: (source) => source,
    format: (source, values) => interpolate(source, values),
  };
  const LocaleContext = createContext<LocaleContextValue>(fallback);

  function LocaleProvider({
    locale,
    catalogue,
    children,
  }: {
    locale: string;
    catalogue?: Catalogue;
    children: ReactNode;
  }) {
    // Rebuilt once per locale change, not per render: a page with a hundred
    // labels would otherwise rebuild the dictionary a hundred times.
    const value = useMemo<LocaleContextValue>(() => {
      const resolved = catalogue ? withoutBlanks(catalogue) : {};
      const translate = (source: string) => resolved[source] ?? source;
      return {
        locale,
        dir: localeDirection(locale),
        t: translate,
        format: (source, values) => interpolate(translate(source), values),
      };
    }, [locale, catalogue]);
    return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
  }

  const useLocale = () => useContext(LocaleContext);

  function T({ children }: { children: ReactNode }) {
    const { t } = useContext(LocaleContext);
    if (typeof children !== "string") return children;
    return t(children);
  }

  function useT() {
    const { t } = useContext(LocaleContext);
    return useCallback((source: string) => t(source), [t]);
  }

  function useFormat() {
    const { format } = useContext(LocaleContext);
    return useCallback((source: string, values: FormatValues) => format(source, values), [format]);
  }

  return { LocaleProvider, useLocale, T, useT, useFormat };
}
