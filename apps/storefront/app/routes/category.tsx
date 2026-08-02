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
import { seoMeta } from "../lib/seo";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const pageNumber = Math.max(1, Number(new URL(request.url).searchParams.get("page")) || 1);
  const country = resolveCountry(request);
  const runtime = catalogueRuntime(context);
  const page = await loadCategoryPage(params.slug, country, runtime, pageNumber);
  if (!page) throw data("Category not found", { status: 404 });
  const popular = await loadBestsellers({ limit: 8, categorySlug: params.slug }, country, runtime);
  return { page, pageNumber, pageSize: CATALOGUE_PAGE_SIZE, popular };
}

export function meta({ data: loaderData }: Route.MetaArgs) {
  return seoMeta(loaderData?.page.seo);
}

export default function CategoryPage({ loaderData }: Route.ComponentProps) {
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
              Sections in {page.name}
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
          {page.productsTotal} product{page.productsTotal === 1 ? "" : "s"}
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
        heading={`Best sellers in ${page.name}`}
        products={popular}
      />
    </>
  );
}
