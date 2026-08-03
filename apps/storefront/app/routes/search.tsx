import { Form, Link } from "react-router";

import type { Route } from "./+types/search";
import { ProductGrid, Section } from "../components/catalogue";
import { ContactForm } from "../components/contact-form";
import {
  catalogueRuntime,
  loadHighlightedProducts,
  loadProductsBySlugs,
  runSearch,
  type SearchGroups,
} from "../lib/catalogue.server";
import { resolveCountry } from "../lib/geo.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { seoMeta } from "../lib/seo";
import { LocalizedText, useLocalizeText } from "../lib/i18n/localized-text";

export async function loader({ request, context }: Route.LoaderArgs) {
  const url = new URL(request.url);
  const country = resolveCountry(request);
  const { locale } = resolveLocale(request);
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
    loadHighlightedProducts(country, runtime, locale.code),
  ]);

  // Product hits become full price cards; slugs come from the search payload
  // (with a path fallback for older API responses). The search match itself
  // runs against English content (the FTS index is not translated), but the
  // cards rendered from those slugs pick up saved translations same as any
  // other product grid.
  const productSlugs = (results.groups.find((group) => group.group === "products")?.items ?? [])
    .map((item) => item.slug ?? item.path.replace("/product/", ""))
    .filter(Boolean);
  const productResults = await loadProductsBySlugs(productSlugs, country, runtime, locale.code);

  return { results, productResults, highlights };
}

export function meta({ data }: Route.MetaArgs) {
  const query = data?.results.query;
  return seoMeta({
    title: query ? `Search: ${query}` : "Search the market",
    description: "Search products, farms, recipes and blog stories.",
    canonicalPath: "/search",
    indexing: "noindex",
  });
}

const GROUP_LABELS: Record<string, string> = {
  farms: "Farms",
  recipes: "Recipes",
  articles: "Blog",
};

export default function SearchPage({ loaderData }: Route.ComponentProps) {
  const localize = useLocalizeText();
  const { results, productResults, highlights } = loaderData;
  const contentGroups = results.groups.filter((group) => group.group !== "products");

  return (
    <>
      <Section eyebrow="Search" heading="What are you looking for?">
        <Form method="get" role="search" className="flex max-w-xl gap-2">
          <label htmlFor="q" className="sr-only">
            <LocalizedText>Search products, farms, recipes and stories</LocalizedText>
          </label>
          <input
            id="q"
            name="q"
            type="search"
            defaultValue={results.query}
            autoFocus
            placeholder={localize("Try “ragi”, “kidney beans” or “Devika”…")}
            className="min-h-11 flex-1 rounded-sm border border-line-strong bg-surface px-4 text-base"
          />
          <button
            type="submit"
            className="min-h-11 rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
          >
            <LocalizedText>Search</LocalizedText>
          </button>
        </Form>

        {results.query && results.total === 0 ? (
          <div className="mt-10 max-w-xl rounded-md border border-dashed border-line-strong px-6 py-10 text-center">
            <p className="font-display text-lg text-ink">
              <LocalizedText>No results for “</LocalizedText>
              {results.query}”
            </p>
            <p className="mt-1 text-sm text-ink-muted">
              <LocalizedText>
                Try a simpler word — we also understand common names like “finger millet” for ragi.
              </LocalizedText>
            </p>
            <div className="mt-4 flex justify-center gap-4 text-sm">
              <Link to="/shop" className="font-medium text-brand hover:underline">
                <LocalizedText>Browse all products</LocalizedText>
              </Link>
              <Link to="/category/fresh-fruits" className="font-medium text-brand hover:underline">
                <LocalizedText>See what is in season</LocalizedText>
              </Link>
            </div>
          </div>
        ) : null}

        {productResults.length > 0 ? (
          <div className="mt-10">
            <h2 className="mb-4 text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
              <LocalizedText>Products</LocalizedText>
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

      {/* Search is where a visitor discovers we do not stock what they came for.
          Rather than end at a dead result set, give them a way to ask — the
          subject arrives pre-filled with their query so the request is
          actionable without any back-and-forth. */}
      <Section
        eyebrow="Still looking?"
        heading="Tell us what you need and we will source it"
        tone="surface"
      >
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="max-w-2xl">
            <ContactForm
              defaultSubject={
                results.query ? `Product request: ${results.query}` : "Product request"
              }
              messagePlaceholder="Which product, quantity and city should we look at?"
              submitLabel="Send request"
              successMessage="Thanks — your request is with our sourcing team. We will reply by email."
            />
          </div>
          <aside className="space-y-5">
            <div>
              <h3 className="font-display text-lg text-ink">
                <LocalizedText>Prefer email?</LocalizedText>
              </h3>
              <a
                href="mailto:support@truegrit.test"
                className="mt-2 block text-sm text-brand underline-offset-4 hover:underline"
              >
                <LocalizedText>support@truegrit.test</LocalizedText>
              </a>
            </div>
            <div>
              <h3 className="font-display text-lg text-ink">
                <LocalizedText>What helps us</LocalizedText>
              </h3>
              <p className="mt-2 text-sm text-ink-muted">
                <LocalizedText>
                  The variety or brand you have in mind, roughly how much you need, and your
                  delivery city.
                </LocalizedText>
              </p>
            </div>
          </aside>
        </div>
      </Section>
    </>
  );
}
