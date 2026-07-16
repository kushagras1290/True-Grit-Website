import type { Route } from "./+types/shop";
import { CategoryTile, ProductGrid, Section } from "../components/catalogue";
import { loadAllProducts, loadCategories } from "../lib/catalogue.server";
import { resolveCountry } from "../lib/geo.server";
import { seoMeta } from "../lib/seo";

export async function loader({ request }: Route.LoaderArgs) {
  const [categories, products] = await Promise.all([
    loadCategories(),
    loadAllProducts(resolveCountry(request)),
  ]);
  return { categories, products };
}

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Shop the market",
    description:
      "Every product in the True Grit market — certified organic, traced to a verified farm.",
    canonicalPath: "/shop",
    indexing: "index",
  });
}

export default function Shop({ loaderData }: Route.ComponentProps) {
  const productCount = loaderData.products.length;
  const categoryCount = loaderData.categories.length;
  return (
    <>
      <header className="bg-canvas">
        <div className="mx-auto max-w-[80rem] px-4 pt-10 pb-8 sm:px-6 md:pt-14">
          <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
            The market
          </p>
          <div className="mt-2 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div className="max-w-2xl">
              <h1 className="font-display text-3xl leading-tight text-ink md:text-4xl">
                Shop the full organic catalogue
              </h1>
              <p className="mt-3 text-base text-ink-muted">
                Browse certified produce, pantry staples and seasonal harvests from verified farms.
              </p>
            </div>
            <p className="text-sm text-ink-muted">
              {categoryCount} categor{categoryCount === 1 ? "y" : "ies"} · {productCount} product
              {productCount === 1 ? "" : "s"}
            </p>
          </div>
        </div>
      </header>
      <Section eyebrow="The market" heading="Shop by food type">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {loaderData.categories.map((category) => (
            <CategoryTile key={category.id} category={category} />
          ))}
        </div>
      </Section>
      <Section eyebrow="Everything" heading="All products" tone="surface">
        <ProductGrid products={loaderData.products} />
      </Section>
    </>
  );
}
