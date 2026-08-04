import { data } from "react-router";

import type { Route } from "./+types/category";
import { Breadcrumbs, CategoryChip, ProductGrid, Section } from "../components/catalogue";
import { PageBanner } from "../components/page-banner";
import { PageLinkPagination } from "../components/pagination";
import { RecommendedProducts } from "../components/recommendations";
import {
  CATALOGUE_PAGE_SIZE,
  catalogueRuntime,
  loadBestsellers,
  loadCategoryPage,
} from "../lib/catalogue.server";
import { resolveCountry } from "../lib/geo.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { seoMeta } from "../lib/seo";
import { LocalizedText, useLocalizeFormat, useLocalizePlural } from "../lib/i18n/localized-text";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const pageNumber = Math.max(1, Number(new URL(request.url).searchParams.get("page")) || 1);
  const country = resolveCountry(request);
  const { locale } = resolveLocale(request);
  const runtime = catalogueRuntime(context);
  const page = await loadCategoryPage(params.slug, country, runtime, pageNumber, locale.code);
  if (!page) throw data("Category not found", { status: 404 });
  const popular = await loadBestsellers(
    { limit: 8, categorySlug: params.slug },
    country,
    runtime,
    locale.code,
  );
  return { page, pageNumber, pageSize: CATALOGUE_PAGE_SIZE, popular };
}

export function meta({ data: loaderData, matches }: Route.MetaArgs) {
  return seoMeta(loaderData?.page.seo, matches);
}

export default function CategoryPage({ loaderData }: Route.ComponentProps) {
  const plural = useLocalizePlural();
  const format = useLocalizeFormat();
  const { page, pageNumber, pageSize, popular } = loaderData;
  return (
    <>
      <Breadcrumbs items={page.breadcrumbs} />
      {/* The same banner frame as the homepage hero and the blog, so every
          category opens with the same shape whether or not an image has been
          uploaded for it — the band is reserved either way, rather than the
          page reflowing the first time someone sets one. */}
      <PageBanner
        imageUrl={page.hero.imageUrl}
        imageAlt={page.hero.imageAlt}
        eyebrow={`${page.hero.eyebrow}${page.hero.seasonLabel ? ` - ${page.hero.seasonLabel}` : ""}`}
        heading={page.hero.title}
        description={page.hero.description}
      />

      <Section>
        {/* A department used to dead-end in a flat grid of everything beneath
            it. Its sections are the natural next step, so they head the grid. */}
        {page.subcategories.length > 0 ? (
          <div className="mb-7">
            <h2 className="mb-3 text-xs font-semibold tracking-[0.14em] text-accent uppercase">
              <LocalizedText>Sections in</LocalizedText> {page.name}
            </h2>
            <ul className="flex flex-wrap gap-2">
              {page.subcategories.map((subcategory) => (
                <li key={subcategory.id}>
                  <CategoryChip
                    label={subcategory.name}
                    count={subcategory.productCount}
                    href={`/category/${subcategory.slug}`}
                  />
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <p className="mb-5 text-sm text-ink-muted" role="status">
          {plural("{count} product", "{count} products", page.productsTotal)}
        </p>
        <ProductGrid products={page.products} />
        <PageLinkPagination page={pageNumber} pageSize={pageSize} total={page.productsTotal} />
      </Section>

      {page.faq.length > 0 ? (
        <Section tone="subtle" eyebrow="Good to know" heading="Questions, answered honestly">
          <dl className="mx-auto grid max-w-4xl gap-6 md:grid-cols-2">
            {page.faq.map((item) => (
              <div key={item.question} className="border-t border-line pt-4">
                <dt className="font-medium text-ink">{item.question}</dt>
                <dd className="mt-1.5 text-sm text-ink-muted">{item.answer}</dd>
              </div>
            ))}
          </dl>
        </Section>
      ) : null}

      <RecommendedProducts
        eyebrow="Popular right now"
        heading={format("Best sellers in {category}", { category: page.name })}
        products={popular}
      />
    </>
  );
}
