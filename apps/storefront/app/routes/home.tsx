import type { Route } from "./+types/home";
import { CmsBlock, type BlockData } from "../components/blocks";
import { loadCategories, loadFarms, loadHome, loadProductsBySlugs } from "../lib/catalogue.server";
import { resolveCountry } from "../lib/geo.server";
import { seoMeta } from "../lib/seo";

export async function loader({ request }: Route.LoaderArgs) {
  const page = await loadHome();
  const productSlugs = page.blocks.flatMap((block) =>
    block.type === "product_collection" ? block.props.productSlugs : [],
  );
  const [categories, farms, products] = await Promise.all([
    loadCategories(),
    loadFarms(),
    loadProductsBySlugs(productSlugs, resolveCountry(request)),
  ]);
  return { page, products, categories, farms };
}

export function meta({ data }: Route.MetaArgs) {
  return seoMeta(data?.page.seo);
}

export default function Home({ loaderData }: Route.ComponentProps) {
  const { page, products, categories, farms } = loaderData;
  const data: BlockData = {
    productsBySlug: new Map(products.map((product) => [product.slug, product])),
    categoriesBySlug: new Map(categories.map((category) => [category.slug, category])),
    farmsBySlug: new Map(farms.map((farm) => [farm.slug, farm])),
  };
  return (
    <>
      {page.blocks.map((block) => (
        <CmsBlock key={block.id} block={block} data={data} />
      ))}
    </>
  );
}
