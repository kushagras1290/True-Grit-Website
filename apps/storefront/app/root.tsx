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
} from "react-router";

import type { Route } from "./+types/root";
import appCss from "./app.css?url";
import { Footer, Header } from "./components/chrome";
import { catalogueRuntime, loadBootstrap, loadSiteSettings } from "./lib/catalogue.server";
import { CartProvider } from "./lib/cart";
import { CurrencyProvider } from "./lib/currency";
import { CustomerProvider } from "./lib/customer-auth";
import { resolveCountry } from "./lib/geo.server";
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
  return {
    bootstrap,
    siteSettings,
    country: resolveCountry(request),
    publicEnv: {
      PUBLIC_API_URL: runtime.apiUrl || process.env.PUBLIC_API_URL || "",
      PUBLIC_FACEBOOK_APP_ID:
        env?.PUBLIC_FACEBOOK_APP_ID || process.env.PUBLIC_FACEBOOK_APP_ID || "",
    },
  };
}

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  const { bootstrap, siteSettings, country, publicEnv } = useLoaderData<typeof loader>();
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
                  <a
                    href="#content"
                    className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-surface focus:px-3 focus:py-2"
                  >
                    Skip to content
                  </a>
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
    </>
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
