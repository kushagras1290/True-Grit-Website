import type { PublicPage } from "@truegrit/contracts";

import type { BlockData } from "../components/blocks";
import {
  catalogueRuntime,
  loadCategories,
  loadFarms,
  loadPage,
  loadProductsBySlugs,
  type CatalogueRuntime,
} from "./catalogue.server";
import { resolveCountry } from "./geo.server";

export interface CmsRouteData {
  page: PublicPage | null;
  blockData: BlockData;
}

export async function loadCmsRoute(
  slug: string,
  request: Request,
  context: unknown,
): Promise<CmsRouteData> {
  const runtime = catalogueRuntime(context);
  const page = await loadPage(slug, runtime);
  return {
    page,
    blockData: page ? await loadBlockData(page, request, runtime) : emptyBlockData(),
  };
}

function emptyBlockData(): BlockData {
  return {
    productsBySlug: new Map(),
    categoriesBySlug: new Map(),
    farmsBySlug: new Map(),
  };
}

async function loadBlockData(
  page: PublicPage,
  request: Request,
  runtime: CatalogueRuntime,
): Promise<BlockData> {
  const productSlugs = page.blocks.flatMap((block) =>
    block.type === "product_collection" ? block.props.productSlugs : [],
  );
  const country = resolveCountry(request);
  const [categories, farms, products] = await Promise.all([
    loadCategories(country, runtime),
    loadFarms(runtime),
    loadProductsBySlugs(productSlugs, country, runtime),
  ]);
  return {
    productsBySlug: new Map(products.map((product) => [product.slug, product])),
    categoriesBySlug: new Map(categories.map((category) => [category.slug, category])),
    farmsBySlug: new Map(farms.map((farm) => [farm.slug, farm])),
  };
}
