/**
 * Deterministic demo catalogue for True Grit.
 *
 * Mirrors `database/seeds/development.sql`. Both frontends fall back to this
 * dataset when no API URL is configured (demo-data mode), so the complete
 * experience is reviewable before Cloudflare resources exist. Never treat this
 * module as a runtime data source once an API is deployed.
 */

import type {
  AdminBundleDetail,
  AnalyticsOverview,
  AdminBundleItem,
  AdminBundleRow,
  AdminCategoryRow,
  AdminInventoryRow,
  AdminOrderRow,
  AdminProductRow,
  AdminPromotionRow,
  AdminReviewRow,
  AdminUserRow,
  ArticleDetail,
  AuditLogRow,
  CategorySummary,
  CustomerAddress,
  FarmDetail,
  FeaturedPromotion,
  FeaturedReview,
  ProductDetail,
  ProductReview,
  PublicBootstrap,
  PublicBundle,
  PublicBundleItem,
  PublicCategoryPage,
  PublicPage,
  RecipeDetail,
  SubscriptionRow,
} from "./index";
import generatedCatalogueJson from "./catalogue.generated.json";

interface GeneratedProductRow {
  id: string;
  name: string;
  slug: string;
  priceMinor: number;
  saleMinor: number | null;
  unitLabel: string;
  availability: ProductDetail["availability"];
  tags: string[];
  imageUrl: string | null;
  imageAlt: string;
  acceptsOrders: boolean;
  leadVariantId: string | null;
  leadSku: string;
  variants: ProductDetail["variants"];
  shortDescription: string;
  certification: string;
  relatedSlugs: string[];
  returnEligible: boolean;
  seoTitle: string;
  seoDescription: string;
  indexing: ProductDetail["seo"]["indexing"];
}

interface GeneratedCatalogueSnapshot {
  generatedFrom: string;
  categories: CategorySummary[];
  products: GeneratedProductRow[];
  categoryProducts: Record<string, string[]>;
}

const generatedCatalogue = generatedCatalogueJson as unknown as GeneratedCatalogueSnapshot;

export const bootstrap: PublicBootstrap = {
  navigation: [
    { label: "Shop", path: "/shop" },
    { label: "Seasonal", path: "/seasonal" },
    { label: "Farmers", path: "/farms" },
    { label: "Recipes", path: "/recipes" },
    { label: "Journal", path: "/journal" },
    { label: "Our Standards", path: "/standards" },
  ],
  footerNavigation: [
    { label: "About", path: "/about" },
    { label: "Delivery", path: "/delivery" },
    { label: "Returns", path: "/returns" },
    { label: "Contact", path: "/contact" },
    { label: "Privacy", path: "/privacy" },
    { label: "Terms", path: "/terms" },
    { label: "Help", path: "/help" },
  ],
  announcement: {
    message: "Alphonso season is here — orchard-fresh boxes ship every Tuesday.",
    path: "/seasonal",
  },
};

/**
 * Demo catalogue tree. Ordered exactly as the public API orders it — each
 * department immediately followed by its own subcategories — so fixture mode
 * exercises the same grouping code path as live data.
 */
export const categories: CategorySummary[] = [
  {
    id: "cat_fresh_fruits",
    name: "Fresh Fruits",
    slug: "fresh-fruits",
    shortDescription: "Seasonal organic fruit, picked at peak ripeness and traced to the orchard.",
    themeKey: "terracotta",
    seasonLabel: "Mango season",
    imageUrl: "/products/organic-alphonso-mangoes.png",
    productCount: 1,
    parentId: null,
    level: 0,
  },
  {
    id: "cat_stone_fruit",
    name: "Stone Fruit",
    slug: "stone-fruit",
    shortDescription: "Mangoes, peaches and plums at the peak of their short season.",
    themeKey: "terracotta",
    seasonLabel: "Mango season",
    imageUrl: null,
    productCount: 1,
    parentId: "cat_fresh_fruits",
    level: 1,
  },
  {
    id: "cat_vegetables",
    name: "Organic Vegetables",
    slug: "organic-vegetables",
    shortDescription: "Everyday vegetables from soil that is tested, rested and certified.",
    themeKey: "sage",
    seasonLabel: null,
    imageUrl: "/products/organic-baby-spinach.png",
    productCount: 1,
    parentId: null,
    level: 0,
  },
  {
    id: "cat_leafy_greens",
    name: "Leafy Greens",
    slug: "leafy-greens",
    shortDescription: "Spinach, amaranth and mustard greens cut to order.",
    themeKey: "sage",
    seasonLabel: null,
    imageUrl: null,
    productCount: 1,
    parentId: "cat_vegetables",
    level: 1,
  },
  {
    id: "cat_grains",
    name: "Grains & Millets",
    slug: "grains-and-millets",
    shortDescription: "Heritage grains and millets, stone-milled in small batches.",
    themeKey: "forest",
    seasonLabel: null,
    imageUrl: "/products/sprouted-ragi-flour.png",
    productCount: 2,
    parentId: null,
    level: 0,
  },
  {
    id: "cat_oils",
    name: "Cold-Pressed Oils",
    slug: "cold-pressed-oils",
    shortDescription: "Wood-pressed and cold-pressed oils from single-origin oilseeds.",
    themeKey: "charcoal",
    seasonLabel: null,
    imageUrl: "/products/wood-pressed-groundnut-oil.png",
    productCount: 1,
    parentId: null,
    level: 0,
  },
];

// The hand-authored launch fixtures above retain their richer copy. The
// generated snapshot fills in every other published seed category so demo mode
// and an API-backed local environment expose the same breadth of catalogue.
const handAuthoredCategoryIds = new Set(categories.map((category) => category.id));
const handAuthoredCategorySlugs = new Set(categories.map((category) => category.slug));
categories.push(
  ...generatedCatalogue.categories.filter(
    (category) =>
      !handAuthoredCategoryIds.has(category.id) && !handAuthoredCategorySlugs.has(category.slug),
  ),
);

export const products: ProductDetail[] = [
  {
    id: "prd_alphonso",
    name: "Organic Alphonso Mangoes",
    slug: "organic-alphonso-mangoes",
    farmName: "Devika Organics",
    farmSlug: "devika-organics",
    region: "Ratnagiri, Maharashtra",
    certification: "India Organic (NPOP)",
    priceMinor: 89900,
    saleMinor: null,
    adjustedMinor: null,
    currencyCode: "INR",
    unitLabel: "1 kg box",
    availability: "in_stock",
    tags: [],
    imageUrl: "/homepage-hero.png",
    imageAlt: "A crate of ripe Alphonso mangoes",
    acceptsOrders: true,
    paymentsOverride: "inherit",
    leadVariantId: "var_alphonso_1kg",
    ratingAverage: 0,
    ratingCount: 0,
    shortDescription: "Ratnagiri Alphonso, tree-ripened and carbide-free, from Devika Organics.",
    overview:
      "Grown on three-generation orchards in Ratnagiri, these Alphonso mangoes ripen on the tree and are packed the same day. No carbide, no cold storage — just fruit at its honest best.",
    storageGuidance: "Keep in a cool, dry place. Refrigerate only once fully ripe.",
    harvestNote: "Harvested weekly through the season; each box carries its picking date.",
    growingMethod: "Certified organic orchard, no synthetic inputs since 1998.",
    variants: [
      {
        id: "var_alphonso_1kg",
        name: "1 kg box (3-4 mangoes)",
        sku: "TRG-MNG-1KG",
        listMinor: 89900,
        saleMinor: null,
        adjustedMinor: null,
        availability: "in_stock",
      },
      {
        id: "var_alphonso_2kg",
        name: "2 kg box (7-8 mangoes)",
        sku: "TRG-MNG-2KG",
        listMinor: 169900,
        saleMinor: 149900,
        adjustedMinor: null,
        availability: "in_stock",
      },
    ],
    traceability: [
      { label: "Farm", detail: "Devika Organics, Ratnagiri — NPOP certificate NPOP/RA/2024/1183" },
      { label: "Harvest", detail: "Tree-ripened, picked at dawn and graded by hand" },
      {
        label: "Quality check",
        detail: "Every lot checked for ripeness and residue-free assurance",
      },
      { label: "Packing", detail: "Packed in ventilated crates the same day" },
      { label: "Delivery", detail: "Ships every Tuesday, orchard to door within 48 hours" },
    ],
    relatedSlugs: ["organic-baby-spinach", "sprouted-ragi-flour"],
    returnEligible: true,
    seo: {
      title: "Organic Alphonso Mangoes — Ratnagiri, carbide-free",
      description:
        "Tree-ripened certified organic Alphonso mangoes from Devika Organics, Ratnagiri.",
      canonicalPath: "/product/organic-alphonso-mangoes",
      indexing: "index",
    },
  },
  {
    id: "prd_spinach",
    name: "Organic Baby Spinach",
    slug: "organic-baby-spinach",
    farmName: "Anandvan Collective",
    farmSlug: "anandvan-collective",
    region: "Wardha, Maharashtra",
    certification: "PGS-India Green",
    priceMinor: 6900,
    saleMinor: null,
    adjustedMinor: null,
    currencyCode: "INR",
    unitLabel: "250 g bunch",
    availability: "in_stock",
    tags: ["Plant Based"],
    imageUrl: "/homepage-hero-greens.png",
    imageAlt: "A fresh bunch of baby spinach leaves",
    acceptsOrders: true,
    paymentsOverride: "inherit",
    leadVariantId: "var_spinach_250g",
    ratingAverage: 4.5,
    ratingCount: 2,
    shortDescription: "Tender baby spinach, harvested at dawn and chilled within the hour.",
    overview:
      "Cut young for tenderness, this spinach comes from rotating beds on regenerated soil. Harvested at dawn, washed in cold spring water and chilled within the hour.",
    storageGuidance: "Refrigerate unwashed in a breathable bag; best within 3 days.",
    harvestNote: "Harvested every morning except Mondays.",
    growingMethod: "PGS-certified beds with compost and neem-based pest management.",
    variants: [
      {
        id: "var_spinach_250g",
        name: "250 g bunch",
        sku: "TRG-SPN-250",
        listMinor: 6900,
        saleMinor: null,
        adjustedMinor: null,
        availability: "in_stock",
      },
    ],
    traceability: [
      { label: "Farm", detail: "Anandvan Collective, Wardha — PGS certificate PGS/MH/2023/0452" },
      { label: "Harvest", detail: "Cut at dawn, chilled within one hour" },
      {
        label: "Quality check",
        detail: "Leaf integrity and freshness check at the collection centre",
      },
      { label: "Packing", detail: "Packed in compostable liners" },
      { label: "Delivery", detail: "Same-day dispatch on a cold chain" },
    ],
    relatedSlugs: ["sprouted-ragi-flour", "wood-pressed-groundnut-oil"],
    returnEligible: true,
    seo: {
      title: "Organic Baby Spinach — harvested at dawn",
      description: "Certified organic baby spinach from the Anandvan Collective.",
      canonicalPath: "/product/organic-baby-spinach",
      indexing: "index",
    },
  },
  {
    id: "prd_ragi",
    name: "Sprouted Ragi Flour",
    slug: "sprouted-ragi-flour",
    farmName: "Anandvan Collective",
    farmSlug: "anandvan-collective",
    region: "Wardha, Maharashtra",
    certification: "PGS-India Green",
    priceMinor: 14500,
    saleMinor: null,
    adjustedMinor: null,
    currencyCode: "INR",
    unitLabel: "500 g pack",
    availability: "in_stock",
    tags: ["Gluten Free", "Traditional Indian"],
    imageUrl: "/products/himalayan-red-rajma.png",
    imageAlt: "Stone-milled ragi flour in a cloth bag",
    acceptsOrders: true,
    paymentsOverride: "inherit",
    leadVariantId: "var_ragi_500g",
    // Its only demo review is still pending moderation — matches the backend
    // rule that only approved reviews count toward the public rating.
    ratingAverage: 0,
    ratingCount: 0,
    shortDescription:
      "Stone-milled finger millet, sprouted for easier digestion and deeper flavour.",
    overview:
      "Finger millet is sprouted for 36 hours, shade-dried and stone-milled in small weekly batches. Sprouting unlocks minerals and gives the flour a naturally sweet, nutty depth.",
    storageGuidance: "Store airtight away from sunlight; use within 3 months.",
    harvestNote: "Milled weekly; each pack shows its milling date.",
    growingMethod: "Rain-fed regenerative plots, PGS-certified.",
    variants: [
      {
        id: "var_ragi_500g",
        name: "500 g pack",
        sku: "TRG-RGI-500",
        listMinor: 14500,
        saleMinor: null,
        adjustedMinor: null,
        availability: "in_stock",
      },
      {
        id: "var_ragi_1kg",
        name: "1 kg pack",
        sku: "TRG-RGI-1KG",
        listMinor: 26900,
        saleMinor: null,
        adjustedMinor: null,
        availability: "in_stock",
      },
    ],
    traceability: [
      {
        label: "Farm",
        detail: "Anandvan Collective, Wardha — 40 family farms on regenerated soil",
      },
      { label: "Harvest", detail: "Rain-fed finger millet, hand-harvested" },
      { label: "Quality check", detail: "Sprouting and moisture checks before milling" },
      { label: "Packing", detail: "Stone-milled and packed in small weekly batches" },
      { label: "Delivery", detail: "Ships within 2 days of milling" },
    ],
    relatedSlugs: ["himalayan-red-rajma", "wood-pressed-groundnut-oil"],
    returnEligible: true,
    seo: {
      title: "Sprouted Ragi Flour — stone-milled finger millet",
      description: "Certified organic sprouted ragi flour from the Anandvan Collective.",
      canonicalPath: "/product/sprouted-ragi-flour",
      indexing: "index",
    },
  },
  {
    id: "prd_groundnut_oil",
    name: "Wood-Pressed Groundnut Oil",
    slug: "wood-pressed-groundnut-oil",
    farmName: "Anandvan Collective",
    farmSlug: "anandvan-collective",
    region: "Wardha, Maharashtra",
    certification: "PGS-India Green",
    priceMinor: 42500,
    saleMinor: null,
    adjustedMinor: null,
    currencyCode: "INR",
    unitLabel: "500 ml bottle",
    availability: "in_stock",
    tags: [],
    imageUrl: "/homepage-hero-citrus.png",
    imageAlt: "A glass bottle of golden groundnut oil",
    acceptsOrders: true,
    paymentsOverride: "inherit",
    leadVariantId: "var_oil_500ml",
    ratingAverage: 3,
    ratingCount: 1,
    shortDescription:
      "Single-origin groundnuts, wood-pressed at low RPM within a week of shelling.",
    overview:
      "Groundnuts from a single harvest are pressed in a traditional wooden ghani at low temperature, keeping aroma and nutrition intact. Settled naturally, never refined or bleached.",
    storageGuidance: "Keep away from direct sunlight. Natural sediment is normal.",
    harvestNote: "Pressed within a week of shelling; bottled the same day.",
    growingMethod: "PGS-certified oilseed plots, wood-pressed at under 40°C.",
    variants: [
      {
        id: "var_oil_500ml",
        name: "500 ml glass bottle",
        sku: "TRG-GNO-500",
        listMinor: 42500,
        saleMinor: null,
        adjustedMinor: null,
        availability: "in_stock",
      },
      {
        id: "var_oil_1l",
        name: "1 L glass bottle",
        sku: "TRG-GNO-1L",
        listMinor: 79900,
        saleMinor: 74900,
        adjustedMinor: null,
        availability: "in_stock",
      },
    ],
    traceability: [
      { label: "Farm", detail: "Anandvan Collective, Wardha — single-origin groundnuts" },
      { label: "Harvest", detail: "Sun-dried and shelled within the collective" },
      { label: "Quality check", detail: "Aflatoxin and moisture screening before pressing" },
      { label: "Packing", detail: "Wood-pressed, settled and bottled in glass" },
      { label: "Delivery", detail: "Ships in protective sleeves within 3 days" },
    ],
    relatedSlugs: ["sprouted-ragi-flour", "organic-baby-spinach"],
    returnEligible: true,
    seo: {
      title: "Wood-Pressed Groundnut Oil — single origin",
      description: "Certified organic wood-pressed groundnut oil from the Anandvan Collective.",
      canonicalPath: "/product/wood-pressed-groundnut-oil",
      indexing: "index",
    },
  },
  {
    id: "prd_rajma",
    name: "Himalayan Red Rajma",
    slug: "himalayan-red-rajma",
    farmName: "Himgiri Terraces",
    farmSlug: "himgiri-terraces",
    region: "Uttarkashi, Uttarakhand",
    certification: "India Organic (NPOP)",
    priceMinor: 19900,
    saleMinor: null,
    adjustedMinor: null,
    currencyCode: "INR",
    unitLabel: "500 g pack",
    availability: "low_stock",
    tags: ["High Protein", "Plant Based"],
    imageUrl: "/homepage-hero-roots.png",
    imageAlt: "Deep red kidney beans from Himalayan terraces",
    acceptsOrders: true,
    paymentsOverride: "inherit",
    leadVariantId: "var_rajma_500g",
    ratingAverage: 4,
    ratingCount: 1,
    shortDescription:
      "Small red kidney beans from high-altitude terraces, famous for their quick cooking.",
    overview:
      "Grown above 1,800 metres on glacial-fed terraces, this small-grain rajma cooks faster and creamier than plains varieties. A Himalayan winter staple, direct from Uttarkashi.",
    storageGuidance: "Store airtight; soak 6-8 hours before cooking.",
    harvestNote: "Single annual harvest, October; current lot is the 2025 harvest.",
    growingMethod: "High-altitude terraces, NPOP-certified, glacial irrigation.",
    variants: [
      {
        id: "var_rajma_500g",
        name: "500 g pack",
        sku: "TRG-RJM-500",
        listMinor: 19900,
        saleMinor: null,
        adjustedMinor: null,
        availability: "low_stock",
      },
    ],
    traceability: [
      {
        label: "Farm",
        detail: "Himgiri Terraces, Uttarkashi — NPOP certificate NPOP/UK/2025/0261",
      },
      { label: "Harvest", detail: "Single October harvest, sun-dried on rooftops" },
      { label: "Quality check", detail: "Hand-sorted for uniform grain size" },
      { label: "Packing", detail: "Packed at origin in 500 g lots" },
      { label: "Delivery", detail: "Ships from the Mumbai fulfilment centre" },
    ],
    relatedSlugs: ["sprouted-ragi-flour"],
    returnEligible: true,
    seo: {
      title: "Himalayan Red Rajma — Uttarkashi terraces",
      description: "Certified organic red rajma grown at altitude by Himgiri Terraces.",
      canonicalPath: "/product/himalayan-red-rajma",
      indexing: "index",
    },
  },
];

function generatedProductDetail(row: GeneratedProductRow): ProductDetail {
  return {
    id: row.id,
    name: row.name,
    slug: row.slug,
    farmName: "True Grit Partner Network",
    farmSlug: "",
    region: "India",
    certification: row.certification,
    priceMinor: row.priceMinor,
    saleMinor: row.saleMinor,
    adjustedMinor: null,
    currencyCode: "INR",
    unitLabel: row.unitLabel,
    availability: row.availability,
    tags: row.tags,
    imageUrl: row.imageUrl,
    imageAlt: row.imageAlt,
    acceptsOrders: row.acceptsOrders,
    // The generated catalogue's demo products all follow the site-wide
    // payments switch -- no fixture row needs a per-product override.
    paymentsOverride: "inherit",
    leadVariantId: row.leadVariantId,
    // The generated catalogue has no demo reviews of its own; the hand-authored
    // products above carry the fixture review data.
    ratingAverage: 0,
    ratingCount: 0,
    shortDescription: row.shortDescription,
    overview: row.shortDescription,
    storageGuidance: "Follow the storage and best-before guidance printed on the current pack.",
    harvestNote: "Lot and packing details are shown on every dispatched item.",
    growingMethod: "Sourced through the True Grit verified producer network.",
    variants: row.variants,
    traceability: [
      { label: "Producer", detail: "True Grit Partner Network — India" },
      { label: "Verification", detail: row.certification },
      {
        label: "Quality check",
        detail: "Checked at the fulfilment centre before dispatch",
      },
      { label: "Delivery", detail: "Shipped with full lot traceability" },
    ],
    relatedSlugs: row.relatedSlugs,
    returnEligible: row.returnEligible,
    seo: {
      title: row.seoTitle,
      description: row.seoDescription,
      canonicalPath: `/product/${row.slug}`,
      indexing: row.indexing,
    },
  };
}

const handAuthoredProductIds = new Set(products.map((product) => product.id));
const handAuthoredProductSlugs = new Set(products.map((product) => product.slug));
const generatedProductsById = new Map(
  generatedCatalogue.products.map((product) => [product.id, product]),
);
for (const product of products) {
  const generated = generatedProductsById.get(product.id);
  if (!generated) continue;
  product.variants = generated.variants;
  product.leadVariantId = generated.leadVariantId;
  product.priceMinor = generated.priceMinor;
  product.saleMinor = generated.saleMinor;
  product.unitLabel = generated.unitLabel;
  product.availability = generated.availability;
}
products.push(
  ...generatedCatalogue.products
    .filter(
      (product) =>
        !handAuthoredProductIds.has(product.id) && !handAuthoredProductSlugs.has(product.slug),
    )
    .map(generatedProductDetail),
);

/**
 * Demo reviews, keyed by product slug. Mirrors `database/seeds/development.sql`
 * — same authors, same copy — so the two environments read as the same store.
 * Only *approved* reviews appear here: `sprouted-ragi-flour`'s one demo review
 * is still pending in the seed, so it is intentionally absent, matching how
 * `ReviewRepository.list_public_for_product` filters on the backend.
 */
export const productReviews: Record<string, ProductReview[]> = {
  "organic-baby-spinach": [
    {
      id: "rev_spinach_1",
      rating: 4,
      title: "Fresh and lasted well",
      body: "Noticeably fresher than what I find at the local market, and it kept for four days in the fridge without wilting.",
      authorName: "Riya Nair",
      verifiedPurchase: true,
      createdAt: "2026-07-17T10:00:00Z",
    },
    {
      id: "rev_spinach_2",
      rating: 5,
      title: "The freshest greens I have had delivered",
      body: "No wilting, no yellowing, straight from the field to the fridge. Genuinely better than anything from the local market.",
      authorName: "Meher Chandra",
      verifiedPurchase: true,
      createdAt: "2026-07-19T10:00:00Z",
    },
  ],
  "himalayan-red-rajma": [
    {
      id: "rev_rajma_1",
      rating: 4,
      title: "Cooks evenly, good flavour",
      body: "Holds its shape well after soaking and cooks in the usual time. Tastes noticeably better than the polished rajma I used to buy.",
      authorName: "Riya Nair",
      verifiedPurchase: true,
      createdAt: "2026-07-21T08:00:00Z",
    },
  ],
  "wood-pressed-groundnut-oil": [
    {
      id: "rev_oil_1",
      rating: 3,
      title: "Good oil, strong smell at first",
      body: "Flavour is good once it settles for a few days, but the bottle smells quite strong straight after opening.",
      authorName: "Arjun Bhatia",
      verifiedPurchase: true,
      createdAt: "2026-07-22T08:00:00Z",
    },
  ],
};

export function reviewsForProduct(slug: string): ProductReview[] {
  return productReviews[slug] ?? [];
}

const allReviewsById = new Map<string, FeaturedReview>();
for (const [slug, list] of Object.entries(productReviews)) {
  const product = products.find((entry) => entry.slug === slug);
  for (const review of list) {
    allReviewsById.set(review.id, {
      ...review,
      productName: product?.name ?? slug,
      productSlug: slug,
    });
  }
}

/**
 * Mirrors `ReviewRepository.list_featured`: `reviewIds` (manual mode) returns
 * exactly those reviews in order; omitted (rule mode) returns the current
 * top-rated reviews sitewide. Demo-mode equivalent of the
 * `/v1/public/reviews/featured` endpoint, used by the homepage
 * `reviews_showcase` block when no API is configured.
 */
export function resolveFeaturedReviews({
  reviewIds,
  minRating = 4,
  limit = 8,
}: {
  reviewIds?: string[];
  minRating?: number;
  limit?: number;
}): FeaturedReview[] {
  if (reviewIds && reviewIds.length > 0) {
    return reviewIds.flatMap((id) => allReviewsById.get(id) ?? []).slice(0, Math.max(limit, 1));
  }
  return [...allReviewsById.values()]
    .filter((review) => review.rating >= minRating)
    .sort((a, b) => b.rating - a.rating || b.createdAt.localeCompare(a.createdAt))
    .slice(0, Math.max(limit, 1));
}

/** Every approved review sitewide, newest first -- backs the demo-mode
 *  fallback for the dedicated `/reviews` page (`GET /v1/public/reviews`). */
export const allApprovedReviews: FeaturedReview[] = [...allReviewsById.values()].sort((a, b) =>
  b.createdAt.localeCompare(a.createdAt),
);

/**
 * Demo coupon/promotion. Mirrors what an admin would configure via the
 * Coupons & Promotions page: a code-gated, active, 15%-off campaign. Backs
 * both the homepage `promotion_banner` block and the checkout-page callout
 * in demo mode, the same single source of truth
 * `GET /v1/public/promotions/featured` is for a live API.
 */
export const featuredPromotionFixture: FeaturedPromotion = {
  id: "promo_demo_welcome15",
  name: "Welcome offer",
  headline: "15% off your first order",
  description: "Use code WELCOME15 at checkout for 15% off orders over ₹500.",
  code: "WELCOME15",
};

export function resolveFeaturedPromotion({
  promotionId,
}: {
  promotionId?: string | null;
} = {}): FeaturedPromotion | null {
  if (promotionId && promotionId !== featuredPromotionFixture.id) return null;
  return featuredPromotionFixture;
}

export const adminPromotions: AdminPromotionRow[] = [
  {
    id: featuredPromotionFixture.id,
    name: featuredPromotionFixture.name,
    status: "active",
    priority: 10,
    startsAt: null,
    endsAt: null,
    stackingPolicy: "exclusive",
    usageLimitTotal: null,
    usageLimitPerCustomer: 1,
    headline: featuredPromotionFixture.headline,
    description: featuredPromotionFixture.description,
    couponCount: 1,
    redemptionCount: 0,
    createdAt: "2026-07-01T00:00:00Z",
    updatedAt: "2026-07-01T00:00:00Z",
  },
];

const bundleFixtureItems: AdminBundleItem[] = [
  {
    id: "bndi_demo_mango",
    variantId: "var_alphonso_1kg",
    quantity: 1,
    variantName: "1 kg box (3-4 mangoes)",
    sku: "TRG-MNG-1KG",
    productId: "prd_alphonso",
    productName: "Organic Alphonso Mangoes",
    productSlug: "organic-alphonso-mangoes",
    imageUrl: "/homepage-hero.png",
    unitPriceMinor: 89900,
    lineTotalMinor: 89900,
  },
  {
    id: "bndi_demo_spinach",
    variantId: "var_spinach_250g",
    quantity: 2,
    variantName: "250 g bunch",
    sku: "TRG-SPN-250",
    productId: "prd_spinach",
    productName: "Organic Baby Spinach",
    productSlug: "organic-baby-spinach",
    imageUrl: "/homepage-hero-greens.png",
    unitPriceMinor: 6900,
    lineTotalMinor: 13800,
  },
];

const bundleFixtureComponentSumMinor = bundleFixtureItems.reduce(
  (sum, item) => sum + item.lineTotalMinor,
  0,
);
const bundleFixtureBundlePriceMinor = 94900;

export const adminBundles: AdminBundleRow[] = [
  {
    id: "bndl_demo_mango_greens",
    name: "Mango & Greens Combo",
    slug: "mango-greens-combo",
    description: "A box of Alphonso mangoes with two bunches of baby spinach, at a set price.",
    status: "active",
    bundlePriceMinor: bundleFixtureBundlePriceMinor,
    imageUrl: "/homepage-hero.png",
    imageAlt: "Alphonso mangoes and baby spinach together",
    itemCount: bundleFixtureItems.length,
    createdAt: "2026-07-01T00:00:00Z",
    updatedAt: "2026-07-01T00:00:00Z",
  },
];

export const adminBundleDetails: Record<string, AdminBundleDetail> = {
  bndl_demo_mango_greens: {
    ...adminBundles[0]!,
    items: bundleFixtureItems,
  },
};

export const publicBundles: PublicBundle[] = [
  {
    id: "bndl_demo_mango_greens",
    name: "Mango & Greens Combo",
    slug: "mango-greens-combo",
    description: "A box of Alphonso mangoes with two bunches of baby spinach, at a set price.",
    bundlePriceMinor: bundleFixtureBundlePriceMinor,
    componentSumMinor: bundleFixtureComponentSumMinor,
    savingsMinor: Math.max(bundleFixtureComponentSumMinor - bundleFixtureBundlePriceMinor, 0),
    imageUrl: "/homepage-hero.png",
    imageAlt: "Alphonso mangoes and baby spinach together",
    items: bundleFixtureItems.map(({ id: _id, ...item }): PublicBundleItem => item),
  },
];

// ---------------------------------------------------------------------------
// Subscriptions ("Subscribe & Save") -- off sitewide by default, so this is
// demo data for the admin support view and the customer's own "My
// Subscriptions" page, not something a fresh demo storefront advertises.
// ---------------------------------------------------------------------------

export const customerAddresses: CustomerAddress[] = [
  {
    id: "addr_demo_home",
    label: "Home",
    recipientName: "Asha Rao",
    phoneE164: "+919999900001",
    line1: "14 Lotus Enclave",
    line2: "Near Community Park",
    city: "Bengaluru",
    state: "Karnataka",
    postalCode: "560034",
    countryCode: "IN",
    isDefaultDelivery: true,
    createdAt: "2026-06-01T00:00:00Z",
  },
];

export const adminSubscriptions: SubscriptionRow[] = [
  {
    id: "sub_demo_mango_weekly",
    customerUserId: "usr_demo_customer",
    variantId: "var_demo_mango_1kg",
    productId: "prd_demo_mango",
    productName: "Alphonso Mango",
    productSlug: "alphonso-mango",
    variantName: "1 kg",
    sku: "MANGO-ALP-1KG",
    imageUrl: "/homepage-hero.png",
    unitPriceMinor: 39900,
    quantity: 2,
    frequency: "weekly",
    status: "active",
    addressId: "addr_demo_home",
    nextOrderDate: "2026-08-08",
    lastOrderId: null,
    createdAt: "2026-07-15T00:00:00Z",
    updatedAt: "2026-07-15T00:00:00Z",
    cancelledAt: null,
    customerName: "Asha Rao",
    customerEmail: "asha.rao@example.com",
  },
];

// ---------------------------------------------------------------------------
// Analytics -- a static 14-day snapshot for the demo dashboard. A live
// deployment computes every figure here from real orders; this is only ever
// shown when no API is configured.
// ---------------------------------------------------------------------------

const analyticsDailyRevenueMinor = [
  62_400, 71_200, 58_900, 84_300, 93_100, 76_800, 68_500, 88_900, 101_200, 79_400, 66_700, 94_600,
  108_300, 91_500,
];

export const analyticsOverview: AnalyticsOverview = {
  fromDate: "2026-07-20",
  toDate: "2026-08-02",
  revenueMinor: analyticsDailyRevenueMinor.reduce((sum, value) => sum + value, 0),
  orderCount: 163,
  averageOrderValueMinor: 6_984,
  newCustomers: 27,
  revenueByDay: analyticsDailyRevenueMinor.map((revenueMinor, index) => {
    const day = new Date("2026-07-20T00:00:00Z");
    day.setUTCDate(day.getUTCDate() + index);
    return {
      date: day.toISOString().slice(0, 10),
      revenueMinor,
      orderCount: Math.max(4, Math.round(revenueMinor / 6_984)),
    };
  }),
  topProducts: [
    {
      productId: "prd_demo_mango",
      productName: "Alphonso Mango",
      unitsSold: 412,
      revenueMinor: 164_400,
    },
    {
      productId: "prd_demo_spinach",
      productName: "Baby Spinach",
      unitsSold: 356,
      revenueMinor: 24_600,
    },
    {
      productId: "prd_demo_rice",
      productName: "Brown Basmati Rice",
      unitsSold: 201,
      revenueMinor: 60_300,
    },
    {
      productId: "prd_demo_greens",
      productName: "Mixed Salad Greens",
      unitsSold: 178,
      revenueMinor: 21_400,
    },
    {
      productId: "prd_demo_honey",
      productName: "Wild Forest Honey",
      unitsSold: 94,
      revenueMinor: 32_900,
    },
  ],
  statusBreakdown: [
    { status: "completed", orderCount: 118 },
    { status: "processing", orderCount: 19 },
    { status: "confirmed", orderCount: 14 },
    { status: "cancelled", orderCount: 8 },
    { status: "pending_payment", orderCount: 4 },
  ],
};

/** Products per category slug. Subcategory entries repeat their department's
 * products, mirroring live data where a product is assigned to both its section
 * and its owning department. */
const categoryProducts: Record<string, string[]> = {
  "fresh-fruits": ["organic-alphonso-mangoes"],
  "stone-fruit": ["organic-alphonso-mangoes"],
  "organic-vegetables": ["organic-baby-spinach"],
  "leafy-greens": ["organic-baby-spinach"],
  "grains-and-millets": ["sprouted-ragi-flour", "himalayan-red-rajma"],
  "cold-pressed-oils": ["wood-pressed-groundnut-oil"],
};

for (const [categorySlug, productSlugs] of Object.entries(generatedCatalogue.categoryProducts)) {
  categoryProducts[categorySlug] = [
    ...new Set([...(categoryProducts[categorySlug] ?? []), ...productSlugs]),
  ];
}

/** Product slugs assigned to a category, for demo-mode filtered grids. */
export function productSlugsForCategory(slug: string): string[] {
  return categoryProducts[slug] ?? [];
}

const categoryHeroes: Record<string, { eyebrow: string; title: string; description: string }> = {
  "fresh-fruits": {
    eyebrow: "In season now",
    title: "Fruit, at its honest best",
    description:
      "Every fruit here is grown without synthetic inputs and travels from a verified farm within days of harvest.",
  },
  "organic-vegetables": {
    eyebrow: "From living soil",
    title: "Vegetables with a story",
    description:
      "Grown by partner farms that practice crop rotation, composting and zero synthetic pesticides.",
  },
  "grains-and-millets": {
    eyebrow: "Slow staples",
    title: "The grains your grandmother knew",
    description:
      "Single-origin millets, rice and pulses from regenerative collectives across India.",
  },
  "cold-pressed-oils": {
    eyebrow: "Pressed, not processed",
    title: "Oil the slow way",
    description:
      "Small-batch oils pressed at low temperature to keep flavour and nutrition intact.",
  },
  "stone-fruit": {
    eyebrow: "Fresh Fruits",
    title: "Stone fruit",
    description:
      "Mangoes, peaches and plums picked at the peak of a season that lasts weeks, not months.",
  },
  "leafy-greens": {
    eyebrow: "Organic Vegetables",
    title: "Leafy greens",
    description: "Spinach, amaranth and mustard greens cut to order and packed the same morning.",
  },
};

export function getCategoryPage(slug: string): PublicCategoryPage | null {
  const category = categories.find((entry) => entry.slug === slug);
  if (!category) return null;
  const parent = categories.find((entry) => entry.id === category.parentId);
  const hero = categoryHeroes[slug] ?? {
    eyebrow: parent?.name ?? "True Grit organic market",
    title: category.name,
    description: category.shortDescription,
  };
  const slugs = categoryProducts[slug] ?? [];
  return {
    id: category.id,
    name: category.name,
    slug: category.slug,
    breadcrumbs: [
      { label: "Home", path: "/" },
      { label: "Shop", path: "/shop" },
      { label: category.name, path: `/category/${category.slug}` },
    ],
    themeKey: category.themeKey,
    hero: {
      ...hero,
      seasonLabel: category.seasonLabel,
      imageUrl: category.imageUrl,
      imageAlt: category.name,
    },
    subcategories: categories.filter((entry) => entry.parentId === category.id),
    products: products.filter((product) => slugs.includes(product.slug)),
    productsTotal: products.filter((product) => slugs.includes(product.slug)).length,
    faq: [
      {
        question: "How do you verify these farms?",
        answer:
          "Every partner farm holds a current NPOP or PGS-India certificate that we verify at onboarding and re-check annually.",
      },
      {
        question: "When is my order harvested?",
        answer:
          "Fresh produce is harvested against confirmed orders, never stockpiled. Pantry goods show their milling or pressing date.",
      },
    ],
    seo: {
      title: `${category.name} — True Grit`,
      description: category.shortDescription,
      canonicalPath: `/category/${category.slug}`,
      indexing: "index",
    },
    updatedAt: "2026-07-02T00:00:00Z",
  };
}

export const farms: FarmDetail[] = [
  {
    id: "farm_devika",
    name: "Devika Organics",
    slug: "devika-organics",
    farmerName: "Devika Kulkarni",
    region: "Ratnagiri, Maharashtra",
    summary: "Three generations of Alphonso orchards farmed without synthetic inputs since 1998.",
    certification: "India Organic (NPOP)",
    establishedYear: 1998,
    story:
      "The Kulkarni family has farmed these laterite slopes above the Arabian Sea for three generations. When Devika took over in 1998, she converted the orchards fully to organic methods — compost pits under every tree, no carbide ripening, and a packing shed a hundred metres from the trees. We never needed chemicals, she says. We needed patience.",
    methods: [
      "Tree-ripening, no carbide",
      "Compost-fed orchards",
      "Hand grading and same-day packing",
    ],
    productSlugs: ["organic-alphonso-mangoes"],
    heroImageUrl: null,
    heroImageAlt: null,
    seo: {
      title: "Devika Organics — Ratnagiri Alphonso orchards",
      description:
        "Certified organic Alphonso mango orchards in Ratnagiri, farmed by the Kulkarni family.",
      canonicalPath: "/farms/devika-organics",
      indexing: "index",
    },
  },
  {
    id: "farm_anandvan",
    name: "Anandvan Collective",
    slug: "anandvan-collective",
    farmerName: "Ravi Patil",
    region: "Wardha, Maharashtra",
    summary:
      "A 40-family collective growing millets, pulses and cold-pressed oilseeds on regenerated soil.",
    certification: "PGS-India Green",
    establishedYear: 2011,
    story:
      "Anandvan began when forty families in Wardha pooled degraded farmland and committed to a ten-year soil regeneration plan. Today the collective grows rain-fed millets and oilseeds, runs its own stone mill and wooden ghani, and shares profits by contributed area.",
    methods: ["Rain-fed cultivation", "Collective stone milling", "Wood-pressed oils under 40°C"],
    productSlugs: ["organic-baby-spinach", "sprouted-ragi-flour", "wood-pressed-groundnut-oil"],
    heroImageUrl: null,
    heroImageAlt: null,
    seo: {
      title: "Anandvan Collective — regenerative millet farming",
      description: "A farmer collective in Wardha growing certified organic millets and pulses.",
      canonicalPath: "/farms/anandvan-collective",
      indexing: "index",
    },
  },
  {
    id: "farm_himgiri",
    name: "Himgiri Terraces",
    slug: "himgiri-terraces",
    farmerName: "Tara Negi",
    region: "Uttarkashi, Uttarakhand",
    summary: "High-altitude terraced farms growing rajma, amaranth and Himalayan spices.",
    certification: "India Organic (NPOP)",
    establishedYear: 2015,
    story:
      "At 1,800 metres in Uttarkashi, Tara Negi organises a network of terraced smallholdings that were organic long before certification existed. Glacial channels irrigate the terraces; the single October harvest is sun-dried on rooftops and hand-sorted through the winter.",
    methods: [
      "High-altitude terracing",
      "Glacial-fed irrigation",
      "Single annual harvest, hand-sorted",
    ],
    productSlugs: ["himalayan-red-rajma"],
    heroImageUrl: null,
    heroImageAlt: null,
    seo: {
      title: "Himgiri Terraces — Himalayan hill farms",
      description:
        "High-altitude organic terraces in Uttarkashi growing rajma, amaranth and spices.",
      canonicalPath: "/farms/himgiri-terraces",
      indexing: "index",
    },
  },
];

export const recipes: RecipeDetail[] = [
  {
    id: "rcp_ragi_dosa",
    title: "Crisp sprouted ragi dosa",
    slug: "crisp-sprouted-ragi-dosa",
    excerpt: "A weekday dosa with the deep, nutty flavour of sprouted finger millet.",
    prepMinutes: 15,
    cookMinutes: 20,
    servings: 4,
    dietaryTags: ["gluten-free", "plant-based"],
    heroImageUrl: "/homepage-hero-roots.png",
    heroImageAlt: "Fresh roots and pulses from organic soil",
    ingredients: [
      { label: "Sprouted ragi flour", quantityText: "2 cups", productSlug: "sprouted-ragi-flour" },
      {
        label: "Baby spinach, chopped",
        quantityText: "1 cup",
        productSlug: "organic-baby-spinach",
      },
      { label: "Groundnut oil", quantityText: "2 tbsp", productSlug: "wood-pressed-groundnut-oil" },
      { label: "Cumin seeds", quantityText: "1 tsp", productSlug: null },
      { label: "Salt", quantityText: "to taste", productSlug: null },
    ],
    blocks: [
      {
        id: "blk_dosa_intro",
        type: "rich_text",
        version: 1,
        enabled: true,
        props: {
          paragraphs: [
            "This dosa uses sprouted [ragi flour](/product/sprouted-ragi-flour) for a nutty batter that crisps fast and needs no overnight fermentation.",
          ],
        },
      },
      {
        id: "blk_dosa_products",
        type: "product_collection",
        version: 1,
        enabled: true,
        props: {
          heading: "Shop this recipe",
          source: "manual",
          productSlugs: [
            "sprouted-ragi-flour",
            "organic-baby-spinach",
            "wood-pressed-groundnut-oil",
          ],
          limit: 4,
        },
      },
    ],
    steps: [
      "Whisk the ragi flour with 2½ cups of water and salt into a thin, pourable batter. Rest 15 minutes.",
      "Fold in the chopped spinach and cumin seeds.",
      "Heat a cast-iron tawa until water beads dance. Wipe with a few drops of groundnut oil.",
      "Pour a ladle of batter from the outside in, lace-style. Drizzle oil around the edge.",
      "Cook 2-3 minutes until the edges lift and crisp. Serve hot with chutney.",
    ],
    seo: {
      title: "Crisp sprouted ragi dosa — True Grit recipes",
      description: "A weekday dosa with the deep, nutty flavour of sprouted finger millet.",
      canonicalPath: "/recipes/crisp-sprouted-ragi-dosa",
      indexing: "index",
    },
  },
];

export const articles: ArticleDetail[] = [
  {
    id: "art_millets",
    title: "The quiet revival of Indian millets",
    slug: "quiet-revival-of-indian-millets",
    excerpt:
      "How a generation of farmers is bringing climate-resilient grains back to the Indian table.",
    authorName: "Kabir Mehta",
    publishedAt: "2026-07-05T00:00:00Z",
    readingMinutes: 6,
    heroImageUrl: "/homepage-hero-roots.png",
    heroImageAlt: "Millet grains and pulses from organic soil",
    blocks: [
      {
        id: "blk_millets_body",
        type: "rich_text",
        version: 1,
        enabled: true,
        props: {
          paragraphs: [
            "For most of the twentieth century, millets fed India. Then subsidised rice and wheat pushed them to the margins — hardy grains recast as poor man's food, grown on the land nobody irrigated.",
            "That story is reversing. Millets need a fraction of the water that rice demands, tolerate heat that wilts wheat, and grow on soil still recovering from decades of intensive farming. For collectives like Anandvan in Wardha, they are not nostalgia — they are the only crop that makes agronomic sense on regenerating land.",
            "The revival is also a flavour story. [Sprouted ragi](/product/sprouted-ragi-flour) has a sweetness that refined flour never had. Little millet cooks into a pilaf with real bite. A generation of cooks is rediscovering grains their grandmothers never abandoned. Try it in our [crisp sprouted ragi dosa](/recipes/crisp-sprouted-ragi-dosa).",
            "What the movement needs now is steady demand: buyers who return every month, not just when a headline celebrates ancient grains. That steadiness is what lets a farmer plant a rain-fed crop with confidence.",
          ],
        },
      },
      {
        id: "blk_millets_products",
        type: "product_collection",
        version: 1,
        enabled: true,
        props: {
          heading: "Shop the grains in this story",
          source: "manual",
          productSlugs: ["sprouted-ragi-flour", "organic-baby-spinach"],
          limit: 4,
        },
      },
    ],
    pullQuote:
      "Millets are not nostalgia — they are the only crop that makes sense on regenerating land.",
    seo: {
      title: "The quiet revival of Indian millets — True Grit blog",
      description:
        "How a generation of farmers is bringing climate-resilient grains back to the Indian table.",
      canonicalPath: "/blog/quiet-revival-of-indian-millets",
      indexing: "index",
    },
  },
];

export const homePage: PublicPage = {
  id: "pag_home",
  slug: "home",
  title: "Food grown the way nature intended",
  blocks: [
    {
      id: "blk_hero",
      type: "hero",
      version: 1,
      enabled: true,
      props: {
        layout: "editorial-split",
        eyebrow: "Certified organic. Fully traceable.",
        heading: "Food grown the way nature intended.",
        text: "Fresh organic produce, conscious pantry essentials and trusted local farms — delivered with complete transparency.",
        imageUrl: "/homepage-hero.png",
        imageAlt: "Organic mangoes held in a sunlit orchard",
        slides: [
          {
            imageUrl: "/homepage-hero.png",
            imageAlt: "Organic mangoes held in a sunlit orchard",
            href: "/shop",
            label: "Explore the market",
            enabled: true,
          },
          {
            imageUrl: "/homepage-hero-tomatoes.png",
            imageAlt: "Organic tomatoes harvested in a mountain field",
            href: "/category/organic-vegetables",
            label: "Shop vegetables",
            enabled: true,
          },
          {
            imageUrl: "/homepage-hero-roots.png",
            imageAlt: "Fresh carrots and beets pulled from organic soil",
            href: "/category/organic-vegetables",
            label: "Shop root vegetables",
            enabled: true,
          },
          {
            imageUrl: "/homepage-hero-greens.png",
            imageAlt: "Fresh leafy greens and herbs held in a farm field",
            href: "/category/organic-vegetables",
            label: "Shop fresh greens",
            enabled: true,
          },
          {
            imageUrl: "/homepage-hero-citrus.png",
            imageAlt: "Seasonal citrus and pears in an organic orchard",
            href: "/seasonal",
            label: "See seasonal fruit",
            enabled: true,
          },
        ],
        primaryAction: { label: "Explore the market", href: "/shop" },
        secondaryAction: { label: "See what is in season", href: "/seasonal" },
      },
    },
    {
      id: "blk_promotion_banner",
      type: "promotion_banner",
      version: 1,
      enabled: true,
      props: {
        source: "rule",
        promotionId: null,
      },
    },
    {
      id: "blk_categories",
      type: "category_collection",
      version: 1,
      enabled: true,
      props: {
        heading: "Shop by food type",
        categorySlugs: [
          "fresh-fruits",
          "organic-vegetables",
          "grains-and-millets",
          "cold-pressed-oils",
        ],
      },
    },
    {
      id: "blk_products",
      type: "product_collection",
      version: 1,
      enabled: true,
      props: {
        heading: "Fresh favourites",
        source: "manual",
        productSlugs: [
          "organic-alphonso-mangoes",
          "organic-baby-spinach",
          "sprouted-ragi-flour",
          "wood-pressed-groundnut-oil",
          "himalayan-red-rajma",
        ],
        limit: 5,
      },
    },
    {
      id: "blk_reviews_showcase",
      type: "reviews_showcase",
      version: 1,
      enabled: true,
      props: {
        heading: "What customers are saying",
        subheading: "Real ratings from verified purchases.",
        source: "rule",
        reviewIds: [],
        limit: 8,
        minRating: 4,
      },
    },
    {
      id: "blk_farmer",
      type: "farmer_story",
      version: 1,
      enabled: true,
      props: {
        farmSlug: "devika-organics",
        quote: "We never needed chemicals. We needed patience.",
        attribution: "Devika Kulkarni, Devika Organics",
      },
    },
    {
      id: "blk_faq",
      type: "faq",
      version: 1,
      enabled: true,
      props: {
        heading: "Our standards",
        items: [
          {
            question: "What does certified organic mean here?",
            answer:
              "Every farm holds a current NPOP or PGS-India certificate that we verify and re-check annually.",
          },
          {
            question: "How is traceability guaranteed?",
            answer:
              "Each lot is tagged at the farm and carries its harvest date, farm and route to your door.",
          },
        ],
      },
    },
    {
      id: "blk_page_links",
      type: "page_links",
      version: 1,
      enabled: true,
      props: {
        heading: "Everything else on True Grit",
        intro:
          "A one-line tour of the rest of the site, so you can find what you need without hunting through the menu.",
        items: [
          {
            label: "Shop the market",
            description: "Every organic product we carry, filtered by food type, farm or price.",
            href: "/shop",
            enabled: true,
          },
          {
            label: "What is in season",
            description:
              "The harvests running right now, so fruit and vegetables arrive at their best.",
            href: "/seasonal",
            enabled: true,
          },
          {
            label: "Our farms",
            description: "The certified growers behind each lot, with their paperwork and methods.",
            href: "/farms",
            enabled: true,
          },
          {
            label: "Recipes",
            description: "Straightforward cooking for the ingredients already in your basket.",
            href: "/recipes",
            enabled: true,
          },
          {
            label: "Journal",
            description: "Practical guides to buying, storing and reading labels on organic food.",
            href: "/blog",
            enabled: true,
          },
          {
            label: "Community",
            description: "Ask a question or compare notes with other customers and growers.",
            href: "/community",
            enabled: true,
          },
          {
            label: "Our standards",
            description: "What certified, traceable and fairly traded actually mean here.",
            href: "/standards",
            enabled: true,
          },
          {
            label: "About True Grit",
            description: "Why the market exists and how it is put together.",
            href: "/about",
            enabled: true,
          },
          {
            label: "Delivery",
            description: "Dispatch days, packing, and what it costs to get an order to you.",
            href: "/delivery",
            enabled: true,
          },
          {
            label: "Returns and refunds",
            description: "What to do when food arrives damaged, late or below standard.",
            href: "/returns",
            enabled: true,
          },
          {
            label: "Help",
            description: "Answers to the questions our support team is asked most often.",
            href: "/help",
            enabled: true,
          },
          {
            label: "Contact us",
            description: "Reach a person about an order, a farm, or anything else.",
            href: "/contact",
            enabled: true,
          },
        ],
      },
    },
    {
      id: "blk_recommendations",
      type: "recommendations",
      version: 1,
      enabled: true,
      props: {
        heading: "Customers' favourites",
        subheading: "Picked by shoppers",
        limit: 8,
      },
    },
    {
      id: "blk_newsletter",
      type: "newsletter",
      version: 1,
      enabled: true,
      props: {
        heading: "A slower, better way to eat.",
        consentText: "One considered letter a month. No noise, unsubscribe anytime.",
      },
    },
  ],
  seo: {
    title: "True Grit — traceable organic food from verified farms",
    description:
      "Fresh organic produce, conscious pantry essentials and trusted local farms — delivered with complete transparency.",
    canonicalPath: "/",
    indexing: "index",
  },
};

// ---------------------------------------------------------------------------
// Admin demo rows
// ---------------------------------------------------------------------------

export const adminProducts: AdminProductRow[] = products.map((product) => ({
  id: product.id,
  name: product.name,
  slug: product.slug,
  imageUrl: product.imageUrl ?? "",
  imageAlt: product.imageAlt,
  sku: product.variants[0]?.sku ?? "—",
  status: "published",
  categories: categories
    .filter((category) => (categoryProducts[category.slug] ?? []).includes(product.slug))
    .map((category) => category.name),
  farmName: product.farmName,
  priceRange:
    product.variants.length > 1
      ? `${product.variants[0]!.listMinor / 100}–${product.variants[product.variants.length - 1]!.listMinor / 100}`
      : `${product.priceMinor / 100}`,
  availableStock: product.availability === "low_stock" ? 8 : 120,
  updatedAt: "2026-07-01T00:00:00Z",
  updatedBy: "Meera Iyer",
}));

export const adminCategories: AdminCategoryRow[] = categories.map((category) => ({
  id: category.id,
  name: category.name,
  imageUrl: category.imageUrl ?? "",
  imageAlt: category.name,
  slug: category.slug,
  parentName: categories.find((parent) => parent.id === category.parentId)?.name ?? null,
  productCount: category.productCount,
  visibility: "public",
  status: "published",
  updatedAt: "2026-07-01T00:00:00Z",
}));

export const adminInventory: AdminInventoryRow[] = [
  {
    variantId: "var_alphonso_1kg",
    productId: "prod_dummy",
    productStatus: "published",
    productName: "Organic Alphonso Mangoes",
    variantName: "1 kg box",
    sku: "TRG-MNG-1KG",
    locationName: "Mumbai Fulfilment Centre",
    onHand: 120,
    reserved: 4,
    reorderThreshold: 20,
    updatedAt: "2026-07-01T00:00:00Z",
  },
  {
    variantId: "var_alphonso_2kg",
    productId: "prod_dummy",
    productStatus: "published",
    productName: "Organic Alphonso Mangoes",
    variantName: "2 kg box",
    sku: "TRG-MNG-2KG",
    locationName: "Mumbai Fulfilment Centre",
    onHand: 60,
    reserved: 2,
    reorderThreshold: 10,
    updatedAt: "2026-07-01T00:00:00Z",
  },
  {
    variantId: "var_spinach_250g",
    productId: "prod_dummy",
    productStatus: "published",
    productName: "Organic Baby Spinach",
    variantName: "250 g bunch",
    sku: "TRG-SPN-250",
    locationName: "Mumbai Fulfilment Centre",
    onHand: 200,
    reserved: 0,
    reorderThreshold: 40,
    updatedAt: "2026-07-01T00:00:00Z",
  },
  {
    variantId: "var_ragi_500g",
    productId: "prod_dummy",
    productStatus: "published",
    productName: "Sprouted Ragi Flour",
    variantName: "500 g pack",
    sku: "TRG-RGI-500",
    locationName: "Mumbai Fulfilment Centre",
    onHand: 340,
    reserved: 0,
    reorderThreshold: 50,
    updatedAt: "2026-07-01T00:00:00Z",
  },
  {
    variantId: "var_ragi_1kg",
    productId: "prod_dummy",
    productStatus: "published",
    productName: "Sprouted Ragi Flour",
    variantName: "1 kg pack",
    sku: "TRG-RGI-1KG",
    locationName: "Mumbai Fulfilment Centre",
    onHand: 180,
    reserved: 0,
    reorderThreshold: 30,
    updatedAt: "2026-07-01T00:00:00Z",
  },
  {
    variantId: "var_oil_500ml",
    productId: "prod_dummy",
    productStatus: "published",
    productName: "Wood-Pressed Groundnut Oil",
    variantName: "500 ml bottle",
    sku: "TRG-GNO-500",
    locationName: "Mumbai Fulfilment Centre",
    onHand: 90,
    reserved: 1,
    reorderThreshold: 15,
    updatedAt: "2026-07-01T00:00:00Z",
  },
  {
    variantId: "var_oil_1l",
    productId: "prod_dummy",
    productStatus: "published",
    productName: "Wood-Pressed Groundnut Oil",
    variantName: "1 L bottle",
    sku: "TRG-GNO-1L",
    locationName: "Mumbai Fulfilment Centre",
    onHand: 45,
    reserved: 0,
    reorderThreshold: 10,
    updatedAt: "2026-07-01T00:00:00Z",
  },
  {
    variantId: "var_rajma_500g",
    productId: "prod_dummy",
    productStatus: "published",
    productName: "Himalayan Red Rajma",
    variantName: "500 g pack",
    sku: "TRG-RJM-500",
    locationName: "Mumbai Fulfilment Centre",
    onHand: 8,
    reserved: 0,
    reorderThreshold: 25,
    updatedAt: "2026-07-01T00:00:00Z",
  },
];

export const adminOrders: AdminOrderRow[] = [
  {
    id: "ord_demo_1",
    publicReference: "TG-9K4M2X",
    customerEmail: "priya@example.test",
    totalMinor: 149900,
    currencyCode: "INR",
    orderStatus: "confirmed",
    paymentStatus: "paid",
    fulfilmentStatus: "packed",
    placedAt: "2026-07-09T08:42:00Z",
  },
  {
    id: "ord_demo_2",
    publicReference: "TG-3D8QLN",
    customerEmail: "arjun@example.test",
    totalMinor: 68300,
    currencyCode: "INR",
    orderStatus: "processing",
    paymentStatus: "paid",
    fulfilmentStatus: "picking",
    placedAt: "2026-07-10T14:05:00Z",
  },
  {
    id: "ord_demo_3",
    publicReference: "TG-7XW1PB",
    customerEmail: "sana@example.test",
    totalMinor: 89900,
    currencyCode: "INR",
    orderStatus: "pending_payment",
    paymentStatus: "pending",
    fulfilmentStatus: "unfulfilled",
    placedAt: "2026-07-11T06:18:00Z",
  },
];

export const adminUsers: AdminUserRow[] = [
  {
    id: "usr_admin",
    displayName: "Asha Rao",
    email: "admin@truegrit.test",
    status: "active",
    roles: ["Super Administrator"],
    lastSignInAt: "2026-07-11T05:00:00Z",
  },
  {
    id: "usr_editor",
    displayName: "Kabir Mehta",
    email: "editor@truegrit.test",
    status: "active",
    roles: ["Content Editor"],
    lastSignInAt: "2026-07-10T16:20:00Z",
  },
  {
    id: "usr_pm",
    displayName: "Meera Iyer",
    email: "catalogue@truegrit.test",
    status: "active",
    roles: ["Product Manager"],
    lastSignInAt: "2026-07-10T11:45:00Z",
  },
  {
    id: "usr_ops",
    displayName: "Dev Sharma",
    email: "ops@truegrit.test",
    status: "active",
    roles: ["Inventory Manager", "Order Manager"],
    lastSignInAt: "2026-07-11T04:10:00Z",
  },
];

export const auditLog: AuditLogRow[] = [
  {
    id: "aud_1",
    actorName: "Asha Rao",
    action: "category.published",
    entityType: "category",
    entityId: "cat_fresh_fruits",
    requestId: "req_01demo1",
    createdAt: "2026-07-02T09:00:00Z",
  },
  {
    id: "aud_2",
    actorName: "Meera Iyer",
    action: "product.published",
    entityType: "product",
    entityId: "prd_alphonso",
    requestId: "req_01demo2",
    createdAt: "2026-07-02T09:12:00Z",
  },
  {
    id: "aud_3",
    actorName: "Dev Sharma",
    action: "inventory.adjusted",
    entityType: "inventory_level",
    entityId: "var_rajma_500g",
    requestId: "req_01demo3",
    createdAt: "2026-07-08T13:30:00Z",
  },
  {
    id: "aud_4",
    actorName: "Kabir Mehta",
    action: "page.draft_saved",
    entityType: "page",
    entityId: "pag_home",
    requestId: "req_01demo4",
    createdAt: "2026-07-10T10:02:00Z",
  },
];

export const adminReviews: AdminReviewRow[] = [
  {
    id: "rev_spinach_1",
    productName: "Organic Baby Spinach",
    productSlug: "organic-baby-spinach",
    rating: 4,
    title: "Fresh and lasted well",
    body: "Noticeably fresher than what I find at the local market, and it kept for four days in the fridge without wilting.",
    status: "approved",
    authorName: "Riya Nair",
    authorEmail: "riya@example.test",
    createdAt: "2026-07-17T10:00:00Z",
    moderatedAt: "2026-07-17T13:00:00Z",
    moderationReason: null,
  },
  {
    id: "rev_spinach_2",
    productName: "Organic Baby Spinach",
    productSlug: "organic-baby-spinach",
    rating: 5,
    title: "The freshest greens I have had delivered",
    body: "No wilting, no yellowing, straight from the field to the fridge. Genuinely better than anything from the local market.",
    status: "approved",
    authorName: "Meher Chandra",
    authorEmail: "meher@example.test",
    createdAt: "2026-07-19T10:00:00Z",
    moderatedAt: "2026-07-19T12:00:00Z",
    moderationReason: null,
  },
  {
    id: "rev_ragi_1",
    productName: "Sprouted Ragi Flour",
    productSlug: "sprouted-ragi-flour",
    rating: 5,
    title: "Great texture for dosas",
    body: "Sprouted ragi makes a noticeably crisper dosa than the usual flour. Will reorder.",
    status: "pending",
    authorName: "Arjun Bhatia",
    authorEmail: "arjun@example.test",
    createdAt: "2026-07-18T09:30:00Z",
    moderatedAt: null,
    moderationReason: null,
  },
  {
    id: "rev_rajma_1",
    productName: "Himalayan Red Rajma",
    productSlug: "himalayan-red-rajma",
    rating: 4,
    title: "Cooks evenly, good flavour",
    body: "Holds its shape well after soaking and cooks in the usual time. Tastes noticeably better than the polished rajma I used to buy.",
    status: "approved",
    authorName: "Riya Nair",
    authorEmail: "riya@example.test",
    createdAt: "2026-07-21T08:00:00Z",
    moderatedAt: "2026-07-21T11:00:00Z",
    moderationReason: null,
  },
  {
    id: "rev_oil_1",
    productName: "Wood-Pressed Groundnut Oil",
    productSlug: "wood-pressed-groundnut-oil",
    rating: 3,
    title: "Good oil, strong smell at first",
    body: "Flavour is good once it settles for a few days, but the bottle smells quite strong straight after opening.",
    status: "approved",
    authorName: "Arjun Bhatia",
    authorEmail: "arjun@example.test",
    createdAt: "2026-07-22T08:00:00Z",
    moderatedAt: "2026-07-22T10:30:00Z",
    moderationReason: null,
  },
];
