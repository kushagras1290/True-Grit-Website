import type {
  FeaturedPromotion,
  FeaturedReview,
  ProductSummary,
  PublicPage,
} from "@truegrit/contracts";

import type { BlockData } from "../components/blocks";
import {
  catalogueRuntime,
  loadBestsellers,
  loadCategories,
  loadFarms,
  loadFeaturedPromotion,
  loadFeaturedReviews,
  loadPage,
  loadProductsBySlugs,
  type CatalogueRuntime,
} from "./catalogue.server";
import { resolveCountry } from "./geo.server";
import { resolveLocale } from "./i18n/resolve.server";

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
  const { locale } = resolveLocale(request);
  const page = await loadPage(slug, runtime, locale.code);
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
    reviewsByBlockId: new Map(),
    promotionsByBlockId: new Map(),
    recommendationsByBlockId: new Map(),
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
  const reviewBlocks = page.blocks.filter(
    (block): block is Extract<PublicPage["blocks"][number], { type: "reviews_showcase" }> =>
      block.type === "reviews_showcase",
  );
  const promotionBlocks = page.blocks.filter(
    (block): block is Extract<PublicPage["blocks"][number], { type: "promotion_banner" }> =>
      block.type === "promotion_banner",
  );
  const recommendationBlocks = page.blocks.filter(
    (block): block is Extract<PublicPage["blocks"][number], { type: "recommendations" }> =>
      block.type === "recommendations",
  );
  const country = resolveCountry(request);
  const [categories, farms, products, reviewLists, promotions, recommendationLists] =
    await Promise.all([
      loadCategories(country, runtime),
      loadFarms(runtime),
      loadProductsBySlugs(productSlugs, country, runtime),
      Promise.all(reviewBlocks.map((block) => loadFeaturedReviews(block, runtime))),
      Promise.all(promotionBlocks.map((block) => loadFeaturedPromotion(block.props, runtime))),
      Promise.all(
        recommendationBlocks.map((block) =>
          loadBestsellers({ limit: block.props.limit }, country, runtime),
        ),
      ),
    ]);
  const reviewsByBlockId = new Map<string, FeaturedReview[]>(
    reviewBlocks.map((block, index) => [block.id, reviewLists[index]!]),
  );
  const promotionsByBlockId = new Map<string, FeaturedPromotion | null>(
    promotionBlocks.map((block, index) => [block.id, promotions[index]!]),
  );
  const recommendationsByBlockId = new Map<string, ProductSummary[]>(
    recommendationBlocks.map((block, index) => [block.id, recommendationLists[index]!]),
  );
  return {
    productsBySlug: new Map(products.map((product) => [product.slug, product])),
    categoriesBySlug: new Map(categories.map((category) => [category.slug, category])),
    farmsBySlug: new Map(farms.map((farm) => [farm.slug, farm])),
    reviewsByBlockId,
    promotionsByBlockId,
    recommendationsByBlockId,
  };
}
