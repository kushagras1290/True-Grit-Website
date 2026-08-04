/**
 * Admin panel localization.
 *
 * Shares the language list and the translation machinery with the storefront
 * (`@truegrit/i18n`) but keeps its own catalogue: the words an operator reads —
 * "Publish", "Inventory", "Audit log" — are a different vocabulary from the
 * words a customer reads, and mixing them would leave both catalogues full of
 * strings the other app never renders.
 *
 * Unlike the storefront, the admin panel is a single-page app with no server
 * render, so the chosen language is read from `localStorage` on mount rather
 * than from a cookie on the server. There is no first-paint flash to avoid
 * here: the operator is already signed in and looking at an app shell, not a
 * page a search engine indexes.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  DEFAULT_LOCALE,
  createLocaleRuntime,
  getLocale,
  isSupportedLocale,
  localeDirection,
  matchAcceptLanguage,
  type Catalogue,
} from "@truegrit/i18n";

import { ADMIN_CATALOGUE_LOADERS } from "./generated-catalogues";

const runtime = createLocaleRuntime();

export const { useLocale, T, useT, useFormat } = runtime;

/** Where the operator's choice is remembered. Scoped to the admin origin, so
 *  it never interferes with the storefront's own language cookie. */
const STORAGE_KEY = "truegrit_admin_lang";

function storedLocale(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value && isSupportedLocale(value) ? value : null;
  } catch {
    // Private browsing and locked-down enterprise profiles can throw on
    // localStorage access. A language preference is not worth a crashed shell.
    return null;
  }
}

function browserLocale(): string | null {
  if (typeof navigator === "undefined") return null;
  const matched = matchAcceptLanguage(navigator.languages?.join(",") ?? navigator.language);
  return matched?.code ?? null;
}

export interface AdminLocaleControls {
  locale: string;
  setLocale: (code: string) => void;
}

/** Separate from the translation context on purpose: only the switcher needs
 *  to *change* the language, and giving every translated label a dependency on
 *  the setter would re-render the entire shell whenever it was recreated. */
const ControlsContext = createContext<AdminLocaleControls>({
  locale: DEFAULT_LOCALE,
  setLocale: () => {},
});

export function useLocaleControls(): AdminLocaleControls {
  return useContext(ControlsContext);
}

export function AdminLocaleProvider({ children }: { children: ReactNode }) {
  // Starts at English and settles on the stored or browser language after
  // mount. Reading storage during the first render would make a server-rendered
  // build disagree with the browser; this app is client-only today, and not
  // depending on that is cheaper than remembering it later.
  const [locale, setLocaleState] = useState<string>(DEFAULT_LOCALE);
  const [catalogue, setCatalogue] = useState<Catalogue | undefined>(undefined);

  useEffect(() => {
    const preferred = storedLocale() ?? browserLocale();
    if (preferred && preferred !== DEFAULT_LOCALE) setLocaleState(preferred);
  }, []);

  // Each language is a separate chunk (see the generator), so switching costs
  // one network request the first time and nothing afterwards. English needs no
  // catalogue at all — it is the source text already in the components.
  useEffect(() => {
    if (locale === DEFAULT_LOCALE) {
      setCatalogue(undefined);
      return;
    }
    const load = ADMIN_CATALOGUE_LOADERS[locale];
    if (!load) {
      setCatalogue(undefined);
      return;
    }
    let active = true;
    load()
      .then((module) => {
        if (active) setCatalogue(module.default);
      })
      .catch(() => {
        // A failed chunk load leaves the panel in English rather than blank.
        if (active) setCatalogue(undefined);
      });
    return () => {
      active = false;
    };
  }, [locale]);

  const setLocale = useCallback((code: string) => {
    if (!isSupportedLocale(code)) return;
    setLocaleState(code);
    try {
      window.localStorage.setItem(STORAGE_KEY, code);
    } catch {
      // Preference is not persisted; the session still switches.
    }
  }, []);

  const controls = useMemo(() => ({ locale, setLocale }), [locale, setLocale]);

  // Right-to-left languages need the document direction, not just translated
  // words — an untouched `dir` leaves Arabic and Urdu laid out backwards.
  useEffect(() => {
    const root = document.documentElement;
    root.lang = locale;
    root.dir = localeDirection(locale);
  }, [locale]);

  return (
    <ControlsContext.Provider value={controls}>
      <runtime.LocaleProvider locale={locale} catalogue={catalogue}>
        {children}
      </runtime.LocaleProvider>
    </ControlsContext.Provider>
  );
}

/** Native name plus English name, for the switcher's option labels. */
export function localeLabel(code: string): string {
  const definition = getLocale(code);
  if (!definition) return code;
  return definition.nativeName === definition.englishName
    ? definition.nativeName
    : `${definition.nativeName} · ${definition.englishName}`;
}
