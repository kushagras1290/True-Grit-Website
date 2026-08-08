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
  LOCALES,
  createLocaleRuntime,
  getLocale,
  isSupportedLocale,
  localeDirection,
  matchAcceptLanguage,
  type Catalogue,
  type LocaleDefinition,
} from "@truegrit/i18n";

import { ADMIN_CATALOGUE_LOADERS } from "./generated-catalogues";
import { adminApiBaseUrl } from "../api";

const runtime = createLocaleRuntime();

export const { useLocale, T, useT, useFormat } = runtime;

/** Where the operator's choice is remembered. Scoped to the admin origin, so
 *  it never interferes with the storefront's own language cookie. */
const STORAGE_KEY = "truegrit_admin_lang";

function storedLocale(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value && /^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}$/.test(value) ? value : null;
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
  locales: readonly LocaleDefinition[];
}

/** Separate from the translation context on purpose: only the switcher needs
 *  to *change* the language, and giving every translated label a dependency on
 *  the setter would re-render the entire shell whenever it was recreated. */
const ControlsContext = createContext<AdminLocaleControls>({
  locale: DEFAULT_LOCALE,
  setLocale: () => {},
  locales: LOCALES,
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
  const [locales, setLocales] = useState<readonly LocaleDefinition[]>(LOCALES);

  useEffect(() => {
    if (!adminApiBaseUrl) return;
    let active = true;
    fetch(`${adminApiBaseUrl}/v1/public/locales/custom`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then(
        (body: {
          items?: Array<{
            code: string;
            nativeName: string;
            englishName: string;
            direction: "ltr" | "rtl";
            groupName: "indian" | "world";
          }>;
        }) => {
          if (!active) return;
          const custom = (body.items ?? []).map(
            (entry) =>
              ({
                code: entry.code,
                nativeName: entry.nativeName,
                englishName: entry.englishName,
                dir: entry.direction,
                group: entry.groupName,
              }) satisfies LocaleDefinition,
          );
          setLocales(
            Array.from(
              new Map(
                [...LOCALES, ...custom].map((entry) => [entry.code.toLowerCase(), entry]),
              ).values(),
            ),
          );
        },
      )
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

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
    let active = true;
    const load = ADMIN_CATALOGUE_LOADERS[locale];
    const localCatalogue = load ? load().then((module) => module.default) : Promise.resolve({});
    const runtimeCatalogue = adminApiBaseUrl
      ? fetch(
          `${adminApiBaseUrl}/v1/public/translations/interface?locale=${encodeURIComponent(locale)}&target=admin`,
          { credentials: "include" },
        ).then(async (response) =>
          response.ok ? (((await response.json()) as { messages?: Catalogue }).messages ?? {}) : {},
        )
      : Promise.resolve({});
    Promise.all([localCatalogue, runtimeCatalogue])
      .then(([generated, overrides]) => {
        if (active) setCatalogue({ ...generated, ...overrides });
      })
      .catch(() => {
        // A failed chunk load leaves the panel in English rather than blank.
        if (active) setCatalogue(undefined);
      });
    return () => {
      active = false;
    };
  }, [locale]);

  const setLocale = useCallback(
    (code: string) => {
      if (!locales.some((entry) => entry.code.toLowerCase() === code.toLowerCase())) return;
      setLocaleState(code);
      try {
        window.localStorage.setItem(STORAGE_KEY, code);
      } catch {
        // Preference is not persisted; the session still switches.
      }
    },
    [locales],
  );

  const controls = useMemo(() => ({ locale, setLocale, locales }), [locale, locales, setLocale]);

  // Right-to-left languages need the document direction, not just translated
  // words — an untouched `dir` leaves Arabic and Urdu laid out backwards.
  useEffect(() => {
    const root = document.documentElement;
    root.lang = locale;
    root.dir =
      locales.find((entry) => entry.code.toLowerCase() === locale.toLowerCase())?.dir ??
      localeDirection(locale);
  }, [locale, locales]);

  return (
    <ControlsContext.Provider value={controls}>
      <runtime.LocaleProvider locale={locale} catalogue={catalogue}>
        {children}
      </runtime.LocaleProvider>
    </ControlsContext.Provider>
  );
}

/** Native name plus English name, for the switcher's option labels. */
export function localeLabel(code: string, locales: readonly LocaleDefinition[] = LOCALES): string {
  const definition =
    locales.find((entry) => entry.code.toLowerCase() === code.toLowerCase()) ?? getLocale(code);
  if (!definition) return code;
  return definition.nativeName === definition.englishName
    ? definition.nativeName
    : `${definition.nativeName} · ${definition.englishName}`;
}
