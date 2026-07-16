import { data } from "react-router";

import type { Route } from "./+types/farm";
import { Breadcrumbs, ProductGrid, Section } from "../components/catalogue";
import { loadFarm, loadProductsBySlugs } from "../lib/catalogue.server";
import { seoMeta } from "../lib/seo";

export async function loader({ params }: Route.LoaderArgs) {
  const farm = await loadFarm(params.slug);
  if (!farm) throw data("Farm not found", { status: 404 });
  return { farm, products: await loadProductsBySlugs(farm.productSlugs) };
}

export function meta({ data: loaderData }: Route.MetaArgs) {
  return seoMeta(loaderData?.farm.seo);
}

export default function FarmPage({ loaderData }: Route.ComponentProps) {
  const { farm, products } = loaderData;
  return (
    <>
      <Breadcrumbs
        items={[
          { label: "Home", path: "/" },
          { label: "Farmers", path: "/farms" },
          { label: farm.name, path: `/farms/${farm.slug}` },
        ]}
      />
      <header className="mx-auto max-w-[80rem] px-4 pt-6 sm:px-6">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
            {farm.region} · since {farm.establishedYear}
          </p>
          <h1 className="mt-2 font-display text-3xl leading-tight text-ink md:text-4xl">
            {farm.name}
          </h1>
          <p className="mt-2 text-base text-ink-muted">Farmed by {farm.farmerName}</p>
          <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-subtle px-3 py-1 text-xs font-medium text-brand">
            <span aria-hidden>✓</span> {farm.certification}
          </p>
        </div>
      </header>

      <Section>
        <div className="grid gap-10 md:grid-cols-[2fr_1fr]">
          <p className="max-w-2xl text-lg leading-relaxed text-ink">{farm.story}</p>
          <div>
            <h2 className="text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
              How they grow
            </h2>
            <ul className="mt-3 space-y-2">
              {farm.methods.map((method) => (
                <li key={method} className="border-l-2 border-accent pl-3 text-sm text-ink">
                  {method}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>

      {products.length > 0 ? (
        <Section eyebrow="From this farm" heading="What they grow for the market" tone="surface">
          <ProductGrid products={products} />
        </Section>
      ) : null}
    </>
  );
}
