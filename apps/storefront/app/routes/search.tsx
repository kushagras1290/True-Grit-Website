import { Form, Link } from "react-router";

import type { Route } from "./+types/search";
import { ProductGrid, Section } from "../components/catalogue";
import {
  catalogueRuntime,
  loadHighlightedProducts,
  loadProductsBySlugs,
  runSearch,
  type SearchGroups,
} from "../lib/catalogue.server";
import { resolveCountry } from "../lib/geo.server";
import { seoMeta } from "../lib/seo";

export async function loader({ request, context }: Route.LoaderArgs) {
  const url = new URL(request.url);
  const country = resolveCountry(request);
  const runtime = catalogueRuntime(context);
  const query = (url.searchParams.get("q") ?? "").slice(0, 120);
  const [results, highlights] = await Promise.all([
    query
      ? runSearch(query, country, runtime)
      : Promise.resolve<SearchGroups>({
          query: "",
          total: 0,
          groups: [],
        }),
    loadHighlightedProducts(country, runtime),
  ]);

  // Product hits become full price cards; slugs come from the search payload
  // (with a path fallback for older API responses).
  const productSlugs = (results.groups.find((group) => group.group === "products")?.items ?? [])
    .map((item) => item.slug ?? item.path.replace("/product/", ""))
    .filter(Boolean);
  const productResults = await loadProductsBySlugs(productSlugs, country, runtime);

  return { results, productResults, highlights };
}

export function meta({ data }: Route.MetaArgs) {
  const query = data?.results.query;
  return seoMeta({
    title: query ? `Search: ${query}` : "Search the market",
    description: "Search products, farms, recipes and journal stories.",
    canonicalPath: "/search",
    indexing: "noindex",
  });
}

const GROUP_LABELS: Record<string, string> = {
  farms: "Farms",
  recipes: "Recipes",
  articles: "Journal",
};

export default function SearchPage({ loaderData }: Route.ComponentProps) {
  const { results, productResults, highlights } = loaderData;
  const contentGroups = results.groups.filter((group) => group.group !== "products");

  return (
    <>
      <Section eyebrow="Search" heading="What are you looking for?">
        <Form method="get" role="search" className="flex max-w-xl gap-2">
          <label htmlFor="q" className="sr-only">
            Search products, farms, recipes and stories
          </label>
          <input
            id="q"
            name="q"
            type="search"
            defaultValue={results.query}
            autoFocus
            placeholder="Try “ragi”, “kidney beans” or “Devika”…"
            className="min-h-11 flex-1 rounded-sm border border-line-strong bg-surface px-4 text-base"
          />
          <button
            type="submit"
            className="min-h-11 rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
          >
            Search
          </button>
        </Form>

        {results.query && results.total === 0 ? (
          <div className="mt-10 max-w-xl rounded-md border border-dashed border-line-strong px-6 py-10 text-center">
            <p className="font-display text-lg text-ink">No results for “{results.query}”</p>
            <p className="mt-1 text-sm text-ink-muted">
              Try a simpler word — we also understand common names like “finger millet” for ragi.
            </p>
            <div className="mt-4 flex justify-center gap-4 text-sm">
              <Link to="/shop" className="font-medium text-brand hover:underline">
                Browse all products
              </Link>
              <Link to="/category/fresh-fruits" className="font-medium text-brand hover:underline">
                See what is in season
              </Link>
            </div>
          </div>
        ) : null}

        {productResults.length > 0 ? (
          <div className="mt-10">
            <h2 className="mb-4 text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
              Products
            </h2>
            <ProductGrid products={productResults} />
          </div>
        ) : null}

        <div className="mt-10 space-y-8">
          {contentGroups.map((group) => (
            <div key={group.group}>
              <h2 className="mb-2 text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
                {GROUP_LABELS[group.group] ?? group.group}
              </h2>
              <ul className="divide-y divide-line rounded-md border border-line bg-surface">
                {group.items.map((item) => (
                  <li key={item.id}>
                    <Link
                      to={item.path}
                      className="flex min-h-11 items-center px-4 text-sm text-ink hover:bg-canvas hover:text-brand"
                    >
                      {item.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      {highlights.length > 0 ? (
        <Section eyebrow="Handpicked" heading="Highlights from the market" tone="subtle">
          <ProductGrid products={highlights} />
        </Section>
      ) : null}
    </>
  );
}
