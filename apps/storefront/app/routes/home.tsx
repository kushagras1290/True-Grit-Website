import type {
  FeaturedPromotion,
  FeaturedReview,
  ProductSummary,
  PublicPage,
} from "@truegrit/contracts";

import type { Route } from "./+types/home";
import { CmsBlock, type BlockData } from "../components/blocks";
import {
  catalogueRuntime,
  loadBestsellers,
  loadCategories,
  loadFarms,
  loadFeaturedPromotion,
  loadFeaturedReviews,
  loadHome,
  loadProductsBySlugs,
} from "../lib/catalogue.server";
import { resolveCountry } from "../lib/geo.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { organizationJsonLd, seoMeta, websiteJsonLd } from "../lib/seo";

export async function loader({ request, context }: Route.LoaderArgs) {
  const runtime = catalogueRuntime(context);
  const country = resolveCountry(request);
  const { locale } = resolveLocale(request);
  const page = await loadHome(country, runtime, locale.code);
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
  const [categories, farms, products, reviewLists, promotions, recommendationLists] =
    await Promise.all([
      loadCategories(country, runtime, locale.code),
      loadFarms(runtime, locale.code),
      loadProductsBySlugs(productSlugs, country, runtime, locale.code),
      Promise.all(reviewBlocks.map((block) => loadFeaturedReviews(block, runtime))),
      Promise.all(promotionBlocks.map((block) => loadFeaturedPromotion(block.props, runtime))),
      Promise.all(
        recommendationBlocks.map((block) =>
          loadBestsellers({ limit: block.props.limit }, country, runtime, locale.code),
        ),
      ),
    ]);
  const reviewsByBlockId: Array<[string, FeaturedReview[]]> = reviewBlocks.map((block, index) => [
    block.id,
    reviewLists[index]!,
  ]);
  const promotionsByBlockId: Array<[string, FeaturedPromotion | null]> = promotionBlocks.map(
    (block, index) => [block.id, promotions[index]!],
  );
  const recommendationsByBlockId: Array<[string, ProductSummary[]]> = recommendationBlocks.map(
    (block, index) => [block.id, recommendationLists[index]!],
  );
  return {
    page,
    products,
    categories,
    farms,
    reviewsByBlockId,
    promotionsByBlockId,
    recommendationsByBlockId,
  };
}

export function meta({ data, matches }: Route.MetaArgs) {
  return [
    ...seoMeta(
      {
        title: "True Grit | Traceable Organic Food from Trusted Farms",
        description:
          "Shop traceable organic food from True Grit — traditional grains, stone-ground flours, pulses, seeds and cold-pressed oils sourced directly from trusted farms.",
        canonicalPath: "/",
        indexing: data?.page.seo.indexing ?? "index",
      },
      matches,
    ),
    organizationJsonLd(),
    websiteJsonLd(),
  ];
}

export default function Home({ loaderData }: Route.ComponentProps) {
  const {
    page,
    products,
    categories,
    farms,
    reviewsByBlockId,
    promotionsByBlockId,
    recommendationsByBlockId,
  } = loaderData;
  const data: BlockData = {
    productsBySlug: new Map(products.map((product) => [product.slug, product])),
    categoriesBySlug: new Map(categories.map((category) => [category.slug, category])),
    farmsBySlug: new Map(farms.map((farm) => [farm.slug, farm])),
    reviewsByBlockId: new Map(reviewsByBlockId),
    promotionsByBlockId: new Map(promotionsByBlockId),
    recommendationsByBlockId: new Map(recommendationsByBlockId),
  };
  return (
    <>
      {page.blocks.map((block) => (
        <CmsBlock key={block.id} block={block} data={data} />
      ))}
    </>
  );
}
