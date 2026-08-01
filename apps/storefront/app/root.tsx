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
import { catalogueRuntime, loadBootstrap, loadSiteSettings } from "./lib/catalogue.server";
import { CartProvider } from "./lib/cart";
import { CurrencyProvider } from "./lib/currency";
import { CustomerProvider } from "./lib/customer-auth";
import { resolveCountry } from "./lib/geo.server";
import { LocaleProvider, useLocaleContext } from "./lib/i18n/context";
import { DEFAULT_LOCALE, localeDirection } from "./lib/i18n/locales";
import { messagesFor } from "./lib/i18n/messages.server";
import { resolveLocale } from "./lib/i18n/resolve.server";
import { SiteSettingsProvider } from "./lib/site-settings";

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
          PUBLIC_FACEBOOK_APP_ID?: string;
        };
      };
    }
  ).cloudflare?.env;
  // Both in one round trip: the header needs the sign-in switches on first
  // paint, or it flashes a button the API would refuse.
  const [bootstrap, siteSettings] = await Promise.all([
    loadBootstrap(runtime),
    loadSiteSettings(runtime),
  ]);
  // Resolved here so the first byte of HTML is already in the visitor's
  // language: switching client-side would paint English, hydrate, then repaint,
  // and would leave crawlers — which never run the script — seeing only
  // English. Only the chosen locale's own entries travel; English is already in
  // the bundle as the fallback (see lib/i18n/messages.ts).
  const locale = resolveLocale(request);
  return {
    bootstrap,
    siteSettings,
    country: resolveCountry(request),
    locale: locale.code,
    dir: locale.dir,
    messages: messagesFor(locale.code),
    publicEnv: {
      PUBLIC_API_URL: runtime.apiUrl || process.env.PUBLIC_API_URL || "",
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

  return (
    <html lang={locale} dir={dir}>
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
  const { bootstrap, siteSettings, country, locale, messages, publicEnv } =
    useLoaderData<typeof loader>();
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
      <LocaleProvider locale={locale} messages={messages}>
        <SiteSettingsProvider settings={siteSettings}>
          <CustomerProvider>
            <CartProvider>
              <CurrencyProvider country={country}>
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
                  </>
                )}
              </CurrencyProvider>
            </CartProvider>
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
        {notFound ? "404" : "Something went wrong"}
      </p>
      <h1 className="mt-3 font-display text-3xl text-ink">
        {notFound ? "This patch is empty." : "We hit a snag."}
      </h1>
      <p className="mt-3 text-sm text-ink-muted">
        {notFound
          ? "The page you are looking for may have moved with the season."
          : "Please try again in a moment. If it persists, the request id in our logs will find it."}
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse"
      >
        Back to the market
      </Link>
    </div>
  );
}
