import { Link } from "react-router";

import type { Route } from "./+types/seasonal";
import { CmsPage } from "../components/cms-page";
import { CategoryTile, ProductGrid, Section } from "../components/catalogue";
import { StaticHero } from "../components/static-page";
import { catalogueRuntime, loadCategories, loadCategoryPage } from "../lib/catalogue.server";
import { loadCmsRoute, type CmsRouteData } from "../lib/cms-route.server";
import { resolveCountry } from "../lib/geo.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { seoMeta } from "../lib/seo";

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

export function meta({ data }: Route.MetaArgs) {
  const cms = data?.cms as CmsRouteData | undefined;
  return seoMeta(cms?.page?.seo ?? fallbackSeo);
}

export default function SeasonalPage({ loaderData }: Route.ComponentProps) {
  if (loaderData.cms.page) {
    return <CmsPage page={loaderData.cms.page} data={loaderData.cms.blockData} />;
  }
  return (
    <>
      <StaticHero
        eyebrow="Seasonal"
        title="What is good right now, not what can sit forever."
        description="Seasonal drops follow harvest windows, weekly packing rhythms and routes that protect freshness from farm to doorstep."
      />

      <Section eyebrow="In season now" heading="Current harvests">
        {loaderData.seasonalProducts.length > 0 ? (
          <ProductGrid products={loaderData.seasonalProducts} />
        ) : (
          <div className="rounded-md border border-dashed border-line-strong px-6 py-14 text-center">
            <p className="font-display text-lg text-ink">Between harvests</p>
            <p className="mt-1 text-sm text-ink-muted">
              The next seasonal drop will appear here when farms confirm availability.
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
              How seasonal works
            </p>
            <h2 className="mt-2 font-display text-3xl text-ink">
              We publish only what farms can stand behind.
            </h2>
            <p className="mt-3 text-base text-ink-muted">
              Some harvests open for a short weekly window, some pantry lots stay available longer,
              and some products disappear until the next crop is ready.
            </p>
          </div>
          <div className="rounded-md border border-line bg-surface p-6">
            <p className="font-medium text-ink">Seasonal updates</p>
            <p className="mt-2 text-sm text-ink-muted">
              Browse the blog for field notes, harvest timing and ingredient ideas tied to the
              current market.
            </p>
            <Link
              to="/blog"
              className="mt-5 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
            >
              Read the blog
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
