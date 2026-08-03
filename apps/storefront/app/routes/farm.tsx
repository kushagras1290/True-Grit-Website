import { data } from "react-router";

import type { Route } from "./+types/farm";
import { Breadcrumbs, ProductGrid, Section } from "../components/catalogue";
import { PageBanner } from "../components/page-banner";
import { catalogueRuntime, loadFarm, loadProductsBySlugs } from "../lib/catalogue.server";
import { resolveCountry } from "../lib/geo.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { seoMeta } from "../lib/seo";
import { LocalizedText } from "../lib/i18n/localized-text";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const runtime = catalogueRuntime(context);
  const { locale } = resolveLocale(request);
  const farm = await loadFarm(params.slug, runtime);
  if (!farm) throw data("Farm not found", { status: 404 });
  return {
    farm,
    products: await loadProductsBySlugs(
      farm.productSlugs,
      resolveCountry(request),
      runtime,
      locale.code,
    ),
  };
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
      {/* Same banner frame as the homepage hero and the blog/farms-listing
          banners. Per-farm, unlike the sitewide farms-listing one -- set on
          this farm's own edit page in the admin, not Site Control. */}
      <PageBanner
        imageUrl={farm.heroImageUrl || "/banners/content/default-market-banner.png"}
        imageAlt={farm.heroImageAlt || farm.name}
        eyebrow={`${farm.region} · since ${farm.establishedYear}`}
        heading={farm.name}
        description={`Farmed by ${farm.farmerName}`}
      />

      <div className="mx-auto max-w-[80rem] px-4 pt-6 sm:px-6">
        <p className="inline-flex items-center gap-1.5 rounded-full bg-subtle px-3 py-1 text-xs font-medium text-brand">
          <span aria-hidden>✓</span> {farm.certification}
        </p>
      </div>

      <Section>
        <div className="grid gap-10 md:grid-cols-[2fr_1fr]">
          <p className="max-w-2xl text-lg leading-relaxed text-ink">{farm.story}</p>
          <div>
            <h2 className="text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
              <LocalizedText>How they grow</LocalizedText>
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
