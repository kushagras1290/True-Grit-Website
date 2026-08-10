import {
  isRouteErrorResponse,
  Link,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useLoaderData,
  useLocation,
  useRouteLoaderData,
} from "react-router";

import type { Route } from "./+types/root";
import appCss from "./app.css?url";
import { Footer, Header } from "./components/chrome";
import { AmbientEffect, CursorTrail } from "./components/effects";
import { LanguageSuggestionPrompt } from "./components/language-suggestion";
import { SupportBotWidget } from "./components/support-bot-widget";
import { NavigationProgress } from "./components/navigation-progress";
import {
  catalogueRuntime,
  loadBootstrap,
  loadCurrencyRates,
  loadCustomLocales,
  loadInterfaceTranslations,
  loadSiteSettings,
} from "./lib/catalogue.server";
import { CartProvider } from "./lib/cart";
import { CurrencyProvider } from "./lib/currency";
import { CustomerProvider } from "./lib/customer-auth";
import { resolveCountry } from "./lib/geo.server";
import { LocaleProvider, useLocaleContext } from "./lib/i18n/context";
import { DEFAULT_LOCALE, LOCALES, localeDirection } from "./lib/i18n/locales";
import { messagesFor } from "./lib/i18n/messages.server";
import { resolveLocale } from "./lib/i18n/resolve.server";
import { DEFAULT_SITE_SETTINGS, SiteSettingsProvider } from "./lib/site-settings";
import { resolveThemeTokens, themeStyleSheet } from "./lib/theme";
import { LocalizedText } from "./lib/i18n/localized-text";
import { WishlistProvider } from "./lib/wishlist";

export const links: Route.LinksFunction = () => [
  { rel: "icon", href: "/favicon.png", type: "image/png" },
  { rel: "apple-touch-icon", href: "/brand/true-grit-mark.webp" },
  { rel: "preconnect", href: "https://fonts.googleapis.com" },
  { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
  {
    rel: "stylesheet",
    href: "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap",
  },
  { rel: "stylesheet", href: appCss },
];

export async function loader({ request, context }: Route.LoaderArgs) {
  const runtime = catalogueRuntime(context);
  const env = (
    context as {
      cloudflare?: {
        env?: {
          PUBLIC_API_URL?: string;
          PUBLIC_GOOGLE_CLIENT_ID?: string;
          PUBLIC_FACEBOOK_APP_ID?: string;
        };
      };
    }
  ).cloudflare?.env;
  // Resolved once and reused for both currency/catalogue (further down) and
  // the settings fetch below, so a visitor's country never has two answers
  // within the same request.
  const country = resolveCountry(request);
  // Resolved before the bootstrap fetch (not after, as previously) so the
  // header/footer navigation labels can be requested in the visitor's
  // language on the very first round trip -- the same reasoning `loadPage`
  // and `loadHome` already follow for CMS content (migration 0067), now
  // extended to database-sourced nav labels (migration 0068).
  const customLocales = await loadCustomLocales(runtime);
  const locales = Array.from(
    new Map(
      [...LOCALES, ...customLocales].map((entry) => [entry.code.toLowerCase(), entry]),
    ).values(),
  );
  const resolved = resolveLocale(request, locales);
  // Both in one round trip: the header needs the sign-in switches on first
  // paint, or it flashes a button the API would refuse.
  const [bootstrap, siteSettings, interfaceTranslations, currencyRates] = await Promise.all([
    loadBootstrap(country, runtime, resolved.locale.code),
    loadSiteSettings(country, runtime),
    loadInterfaceTranslations(resolved.locale.code, runtime),
    loadCurrencyRates(runtime),
  ]);
  // Resolved here so the first byte of HTML is already in the visitor's
  // language: switching client-side would paint English, hydrate, then repaint,
  // and would leave crawlers — which never run the script — seeing only
  // English. Only the chosen locale's own entries travel; English is already in
  // the bundle as the fallback (see lib/i18n/messages.ts).
  return {
    bootstrap,
    siteSettings,
    country,
    locale: resolved.locale.code,
    dir: resolved.locale.dir,
    locales,
    // Only ever "geo" when it matters: whether this language was guessed from
    // the visitor's country rather than something they told us (a cookie, a
    // link, or their own browser). `LanguageSuggestionPrompt` reads this to
    // decide whether to offer a way back to English.
    localeSource: resolved.source,
    messages: { ...messagesFor(resolved.locale.code), ...interfaceTranslations },
    currencyRates,
    publicEnv: {
      PUBLIC_API_URL: runtime.apiUrl || process.env.PUBLIC_API_URL || "",
      PUBLIC_GOOGLE_CLIENT_ID:
        env?.PUBLIC_GOOGLE_CLIENT_ID || process.env.PUBLIC_GOOGLE_CLIENT_ID || "",
      PUBLIC_FACEBOOK_APP_ID:
        env?.PUBLIC_FACEBOOK_APP_ID || process.env.PUBLIC_FACEBOOK_APP_ID || "",
    },
  };
}

export function Layout({ children }: { children: React.ReactNode }) {
  // `useRouteLoaderData` rather than `useLoaderData`: Layout also wraps the
  // error boundary, which renders when the root loader threw and there is no
  // data at all. Falling back to English there keeps a 500 page rendering
  // instead of compounding the failure.
  const rootData = useRouteLoaderData<typeof loader>("root");
  const locale = rootData?.locale ?? DEFAULT_LOCALE;
  const dir = rootData?.dir ?? localeDirection(locale);
  const { pathname } = useLocation();
  // Resolved per render, in `<head>`, and after `<Links>` so it outranks the
  // stylesheet it is overriding. Server-rendered rather than applied on
  // hydration: a theme that arrived with the JavaScript would repaint the page
  // in front of the visitor on every first load.
  const themeCss = themeStyleSheet(
    resolveThemeTokens(rootData?.siteSettings.theme ?? DEFAULT_SITE_SETTINGS.theme, pathname),
  );

  return (
    <html lang={locale} dir={dir} suppressHydrationWarning>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {/* Every language is the same URL with a different cookie, so there is
            no per-locale href to advertise; `x-default` tells crawlers the
            canonical is language-neutral rather than leaving them to guess that
            each visit's language is a separate page. */}
        <link rel="alternate" hrefLang="x-default" href="/" />
        <Meta />
        <Links />
        {/* Values are validated against a colour allow-list before they are
            interpolated (`lib/theme.isValidThemeColor`), so this cannot carry a
            stray `}` out of the declaration block. */}
        {themeCss ? (
          <style data-truegrit-theme dangerouslySetInnerHTML={{ __html: themeCss }} />
        ) : null}
      </head>
      <body>
        {/* Marks the document as scripted before first paint, so controls with
            a no-JavaScript fallback (the language switcher's submit button)
            can hide it without a flash. Inline and synchronous by necessity:
            anything deferred lands after the button has already been seen. */}
        <script
          dangerouslySetInnerHTML={{
            __html: 'document.documentElement.classList.add("js-enabled");',
          }}
        />
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  const {
    bootstrap,
    siteSettings,
    country,
    locale,
    locales,
    localeSource,
    messages,
    currencyRates,
    publicEnv,
  } = useLoaderData<typeof loader>();
  const location = useLocation();
  const isPaymentWindow = location.pathname === "/payment/razorpay";
  return (
    <>
      <script
        dangerouslySetInnerHTML={{
          __html: `window.__TRUEGRIT_PUBLIC_ENV__=${JSON.stringify(publicEnv).replace(
            /</g,
            "\\u003c",
          )};`,
        }}
      />
      <NavigationProgress />
      <LocaleProvider locale={locale} messages={messages} locales={locales}>
        <SiteSettingsProvider settings={siteSettings}>
          <CustomerProvider>
            <WishlistProvider>
              <CartProvider>
                <CurrencyProvider country={country} rates={currencyRates}>
                  {isPaymentWindow ? (
                    <main id="content">
                      <Outlet />
                    </main>
                  ) : (
                    <>
                      <SkipLink />
                      <Header bootstrap={bootstrap} />
                      <main id="content">
                        <Outlet />
                      </main>
                      <Footer bootstrap={bootstrap} />
                      {/* Decoration only, and never on the payment window: a
                          snowfall over a card form is a distraction at exactly
                          the wrong moment. Both layers no-op for a visitor who
                          asked for reduced motion. */}
                      <AmbientEffect
                        effect={siteSettings.effects.ambient.effect}
                        color={siteSettings.effects.ambient.color}
                        intensity={siteSettings.effects.ambient.intensity}
                      />
                      <CursorTrail
                        trail={siteSettings.effects.cursor.trail}
                        color={siteSettings.effects.cursor.color}
                        hideNativeCursor={siteSettings.effects.cursor.hideNativeCursor}
                      />
                      <LanguageSuggestionPrompt locale={locale} active={localeSource === "geo"} />
                      <SupportBotWidget country={country} />
                    </>
                  )}
                </CurrencyProvider>
              </CartProvider>
            </WishlistProvider>
          </CustomerProvider>
        </SiteSettingsProvider>
      </LocaleProvider>
    </>
  );
}

/** Split out only so it can sit inside `LocaleProvider` and be translated —
 *  the first thing a keyboard or screen-reader user hears should not be the one
 *  English string on the page. */
function SkipLink() {
  const { t } = useLocaleContext();
  return (
    <a
      href="#content"
      className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-surface focus:px-3 focus:py-2"
    >
      {t("common.skipToContent")}
    </a>
  );
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  const notFound = isRouteErrorResponse(error) && error.status === 404;
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center">
      <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
        {notFound ? "404" : <LocalizedText>{"Something went wrong"}</LocalizedText>}
      </p>
      <h1 className="mt-3 font-display text-3xl text-ink">
        {notFound ? (
          <LocalizedText>{"This patch is empty."}</LocalizedText>
        ) : (
          <LocalizedText>{"We hit a snag."}</LocalizedText>
        )}
      </h1>
      <p className="mt-3 text-sm text-ink-muted">
        {notFound ? (
          <LocalizedText>
            {"The page you are looking for may have moved with the season."}
          </LocalizedText>
        ) : (
          <LocalizedText>
            {
              "Please try again in a moment. If it persists, the request id in our logs will find it."
            }
          </LocalizedText>
        )}
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse"
      >
        <LocalizedText>Back to the market</LocalizedText>
      </Link>
    </div>
  );
}
