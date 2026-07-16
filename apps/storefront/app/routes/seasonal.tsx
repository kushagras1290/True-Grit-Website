import { Link } from "react-router";

import type { Route } from "./+types/seasonal";
import { CategoryTile, ProductGrid, Section } from "../components/catalogue";
import { StaticHero } from "../components/static-page";
import { loadCategories, loadProductsBySlugs } from "../lib/catalogue.server";
import { seoMeta } from "../lib/seo";
import { products as allProducts } from "@truegrit/contracts/fixtures";

export async function loader() {
  const categories = await loadCategories();
  const seasonalCategories = categories.filter((category) => category.seasonLabel);
  // The curated seasonal slot: in-season drops, selected by the demo fixture's
  // slug convention. The product data itself is loaded live when the API is on.
  const seasonalProducts = await loadProductsBySlugs(
    allProducts
      .filter(
        (product) => product.availability !== "out_of_stock" && product.slug.includes("mango"),
      )
      .map((product) => product.slug),
  );

  return { seasonalCategories, seasonalProducts };
}

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Seasonal market",
    description:
      "Fresh organic harvests and limited seasonal drops from True Grit's verified farm network.",
    canonicalPath: "/seasonal",
    indexing: "index",
  });
}

export default function SeasonalPage({ loaderData }: Route.ComponentProps) {
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
              Browse the journal for field notes, harvest timing and ingredient ideas tied to the
              current market.
            </p>
            <Link
              to="/journal"
              className="mt-5 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
            >
              Read the journal
            </Link>
          </div>
        </div>
      </Section>
    </>
  );
}
