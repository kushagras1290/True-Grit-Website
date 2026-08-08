import { Link } from "react-router";
import { useEffect, useState } from "react";

import type { Route } from "./+types/seasonal";
import { CmsPage } from "../components/cms-page";
import { CategoryTile, ProductGrid, Section } from "../components/catalogue";
import { StaticHero } from "../components/static-page";
import { catalogueRuntime, loadCategories, loadCategoryPage } from "../lib/catalogue.server";
import { loadCmsRoute, type CmsRouteData } from "../lib/cms-route.server";
import { resolveCountry } from "../lib/geo.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { seoMeta } from "../lib/seo";
import { LocalizedText } from "../lib/i18n/localized-text";
import { commerceLive, getSeasonalCalendar, type SeasonalWindowInfo } from "../lib/commerce";
import { useSiteSettings } from "../lib/site-settings";

export async function loader({ request, context }: Route.LoaderArgs) {
  const runtime = catalogueRuntime(context);
  const country = resolveCountry(request);
  const { locale } = resolveLocale(request);
  const [cms, categories] = await Promise.all([
    loadCmsRoute("seasonal", request, context),
    loadCategories(country, runtime, locale.code),
  ]);
  const seasonalCategories = categories.filter((category) => category.seasonLabel);
  const seasonalPages = await Promise.all(
    seasonalCategories.map((category) =>
      loadCategoryPage(category.slug, country, runtime, 1, locale.code),
    ),
  );
  const seasonalProducts = Array.from(
    new Map(
      seasonalPages
        .flatMap((page) => page?.products ?? [])
        .filter((product) => product.availability !== "out_of_stock")
        .map((product) => [product.slug, product]),
    ).values(),
  );

  return { cms, seasonalCategories, seasonalProducts };
}

const fallbackSeo = {
  title: "Seasonal market",
  description:
    "Fresh organic harvests and limited seasonal drops from True Grit's verified farm network.",
  canonicalPath: "/seasonal",
  indexing: "index",
} as const;

export function meta({ data, matches }: Route.MetaArgs) {
  const cms = data?.cms as CmsRouteData | undefined;
  return seoMeta(cms?.page?.seo ?? fallbackSeo, matches);
}

export default function SeasonalPage({ loaderData }: Route.ComponentProps) {
  const { preorders } = useSiteSettings();
  const [calendar, setCalendar] = useState<SeasonalWindowInfo[]>([]);
  useEffect(() => {
    if (!commerceLive || !preorders.enabled) return;
    let active = true;
    getSeasonalCalendar()
      .then((items) => {
        if (active) setCalendar(items);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [preorders.enabled]);

  if (loaderData.cms.page) {
    return (
      <>
        <CmsPage page={loaderData.cms.page} data={loaderData.cms.blockData} />
        {preorders.enabled && calendar.length > 0 ? (
          <Section eyebrow="Reserve the next harvest" heading="Harvest calendar">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {calendar.map((window) => (
                <article key={window.id} className="rounded-md border border-line bg-surface p-5">
                  <p className="text-xs font-semibold tracking-[0.12em] text-accent uppercase">
                    {window.expectedStart} – {window.expectedEnd}
                  </p>
                  <h3 className="mt-2 font-display text-xl text-ink">
                    {window.title || window.productName}
                  </h3>
                  <Link
                    to={`/product/${window.productSlug}?preorder=1`}
                    className="mt-5 inline-flex min-h-11 items-center rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-90"
                  >
                    <LocalizedText>Reserve this harvest</LocalizedText>
                  </Link>
                </article>
              ))}
            </div>
          </Section>
        ) : null}
      </>
    );
  }
  return (
    <>
      <StaticHero
        eyebrow="Seasonal"
        title="What is good right now, not what can sit forever."
        description="Seasonal drops follow harvest windows, weekly packing rhythms and routes that protect freshness from farm to doorstep."
      />

      {preorders.enabled && calendar.length > 0 ? (
        <Section eyebrow="Reserve the next harvest" heading="Harvest calendar">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {calendar.map((window) => (
              <article key={window.id} className="rounded-md border border-line bg-surface p-5">
                <p className="text-xs font-semibold tracking-[0.12em] text-accent uppercase">
                  {window.expectedStart} – {window.expectedEnd}
                </p>
                <h3 className="mt-2 font-display text-xl text-ink">
                  {window.title || window.productName}
                </h3>
                <p className="mt-2 text-sm text-ink-muted">
                  {window.maxPreorders
                    ? `${window.currentPreorders} of ${window.maxPreorders} reservations taken`
                    : <LocalizedText>{"Reservations are open"}</LocalizedText>}
                </p>
                <Link
                  to={`/product/${window.productSlug}?preorder=1`}
                  className="mt-5 inline-flex min-h-11 items-center rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-90"
                >
                  <LocalizedText>Reserve this harvest</LocalizedText>
                </Link>
              </article>
            ))}
          </div>
        </Section>
      ) : null}

      <Section eyebrow="In season now" heading="Current harvests">
        {loaderData.seasonalProducts.length > 0 ? (
          <ProductGrid products={loaderData.seasonalProducts} />
        ) : (
          <div className="rounded-md border border-dashed border-line-strong px-6 py-14 text-center">
            <p className="font-display text-lg text-ink">
              <LocalizedText>Between harvests</LocalizedText>
            </p>
            <p className="mt-1 text-sm text-ink-muted">
              <LocalizedText>
                The next seasonal drop will appear here when farms confirm availability.
              </LocalizedText>
            </p>
          </div>
        )}
      </Section>

      <Section tone="surface" eyebrow="Seasonal categories" heading="Browse by harvest type">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {loaderData.seasonalCategories.map((category) => (
            <CategoryTile key={category.id} category={category} />
          ))}
        </div>
      </Section>

      <Section tone="subtle">
        <div className="grid gap-8 md:grid-cols-[1fr_1fr] md:items-center">
          <div>
            <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
              <LocalizedText>How seasonal works</LocalizedText>
            </p>
            <h2 className="mt-2 font-display text-3xl text-ink">
              <LocalizedText>We publish only what farms can stand behind.</LocalizedText>
            </h2>
            <p className="mt-3 text-base text-ink-muted">
              <LocalizedText>
                Some harvests open for a short weekly window, some pantry lots stay available
                longer, and some products disappear until the next crop is ready.
              </LocalizedText>
            </p>
          </div>
          <div className="rounded-md border border-line bg-surface p-6">
            <p className="font-medium text-ink">
              <LocalizedText>Seasonal updates</LocalizedText>
            </p>
            <p className="mt-2 text-sm text-ink-muted">
              <LocalizedText>
                Browse the blog for field notes, harvest timing and ingredient ideas tied to the
                current market.
              </LocalizedText>
            </p>
            <Link
              to="/blog"
              className="mt-5 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
            >
              <LocalizedText>Read the blog</LocalizedText>
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
