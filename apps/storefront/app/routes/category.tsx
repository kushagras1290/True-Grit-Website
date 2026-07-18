import { data } from "react-router";

import type { Route } from "./+types/category";
import { Breadcrumbs, ProductGrid, Section } from "../components/catalogue";
import { PageLinkPagination } from "../components/pagination";
import { CATALOGUE_PAGE_SIZE, catalogueRuntime, loadCategoryPage } from "../lib/catalogue.server";
import { resolveCountry } from "../lib/geo.server";
import { seoMeta } from "../lib/seo";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const pageNumber = Math.max(1, Number(new URL(request.url).searchParams.get("page")) || 1);
  const page = await loadCategoryPage(
    params.slug,
    resolveCountry(request),
    catalogueRuntime(context),
    pageNumber,
  );
  if (!page) throw data("Category not found", { status: 404 });
  return { page, pageNumber, pageSize: CATALOGUE_PAGE_SIZE };
}

export function meta({ data: loaderData }: Route.MetaArgs) {
  return seoMeta(loaderData?.page.seo);
}

export default function CategoryPage({ loaderData }: Route.ComponentProps) {
  const { page, pageNumber, pageSize } = loaderData;
  return (
    <>
      <Breadcrumbs items={page.breadcrumbs} />
      <header className="mx-auto max-w-[80rem] px-4 pt-6 pb-2 sm:px-6">
        <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_24rem] md:items-end">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
              {page.hero.eyebrow}
              {page.hero.seasonLabel ? ` - ${page.hero.seasonLabel}` : ""}
            </p>
            <h1 className="mt-2 font-display text-3xl leading-tight text-ink md:text-4xl">
              {page.hero.title}
            </h1>
            <p className="mt-3 text-base text-ink-muted">{page.hero.description}</p>
          </div>
          {page.hero.imageUrl ? (
            <img
              src={page.hero.imageUrl}
              alt={page.hero.imageAlt ?? ""}
              className="aspect-[4/3] w-full rounded-md object-cover"
            />
          ) : null}
        </div>
      </header>

      <Section>
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
    </>
  );
}
