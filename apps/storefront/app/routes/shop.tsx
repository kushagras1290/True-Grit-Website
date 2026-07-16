import type { Route } from "./+types/shop";
import { CategoryTile, ProductGrid, Section } from "../components/catalogue";
import { loadAllProducts, loadCategories } from "../lib/catalogue.server";
import { seoMeta } from "../lib/seo";

export async function loader() {
  const [categories, products] = await Promise.all([loadCategories(), loadAllProducts()]);
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
  return (
    <>
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
