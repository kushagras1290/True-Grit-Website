/**
 * Deterministic demo catalogue for True Grit.
 *
 * Mirrors `database/seeds/development.sql`. Both frontends fall back to this
 * dataset when no API URL is configured (demo-data mode), so the complete
 * experience is reviewable before Cloudflare resources exist. Never treat this
 * module as a runtime data source once an API is deployed.
 */

import type {
  AdminCategoryRow,
  AdminInventoryRow,
  AdminOrderRow,
  AdminProductRow,
  AdminUserRow,
  ArticleDetail,
  AuditLogRow,
  CategorySummary,
  FarmDetail,
  ProductDetail,
  PublicBootstrap,
  PublicCategoryPage,
  PublicPage,
  RecipeDetail,
} from "./index";

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

export const categories: CategorySummary[] = [
  {
    id: "cat_fresh_fruits",
    name: "Fresh Fruits",
    slug: "fresh-fruits",
    shortDescription: "Seasonal organic fruit, picked at peak ripeness and traced to the orchard.",
    themeKey: "terracotta",
    seasonLabel: "Mango season",
    imageUrl: null,
    productCount: 1,
  },
  {
    id: "cat_vegetables",
    name: "Organic Vegetables",
    slug: "organic-vegetables",
    shortDescription: "Everyday vegetables from soil that is tested, rested and certified.",
    themeKey: "sage",
    seasonLabel: null,
    imageUrl: null,
    productCount: 1,
  },
  {
    id: "cat_grains",
    name: "Grains & Millets",
    slug: "grains-and-millets",
    shortDescription: "Heritage grains and millets, stone-milled in small batches.",
    themeKey: "forest",
    seasonLabel: null,
    imageUrl: null,
    productCount: 2,
  },
  {
    id: "cat_oils",
    name: "Cold-Pressed Oils",
    slug: "cold-pressed-oils",
    shortDescription: "Wood-pressed and cold-pressed oils from single-origin oilseeds.",
    themeKey: "charcoal",
    seasonLabel: null,
    imageUrl: null,
    productCount: 1,
  },
];

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
    currencyCode: "INR",
    unitLabel: "1 kg box",
    availability: "in_stock",
    tags: [],
    imageUrl: null,
    imageAlt: "A crate of ripe Alphonso mangoes",
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
        availability: "in_stock",
      },
      {
        id: "var_alphonso_2kg",
        name: "2 kg box (7-8 mangoes)",
        sku: "TRG-MNG-2KG",
        listMinor: 169900,
        saleMinor: 149900,
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
    currencyCode: "INR",
    unitLabel: "250 g bunch",
    availability: "in_stock",
    tags: ["Plant Based"],
    imageUrl: null,
    imageAlt: "A fresh bunch of baby spinach leaves",
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
    currencyCode: "INR",
    unitLabel: "500 g pack",
    availability: "in_stock",
    tags: ["Gluten Free", "Traditional Indian"],
    imageUrl: null,
    imageAlt: "Stone-milled ragi flour in a cloth bag",
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
        availability: "in_stock",
      },
      {
        id: "var_ragi_1kg",
        name: "1 kg pack",
        sku: "TRG-RGI-1KG",
        listMinor: 26900,
        saleMinor: null,
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
    currencyCode: "INR",
    unitLabel: "500 ml bottle",
    availability: "in_stock",
    tags: [],
    imageUrl: null,
    imageAlt: "A glass bottle of golden groundnut oil",
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
        availability: "in_stock",
      },
      {
        id: "var_oil_1l",
        name: "1 L glass bottle",
        sku: "TRG-GNO-1L",
        listMinor: 79900,
        saleMinor: 74900,
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
    currencyCode: "INR",
    unitLabel: "500 g pack",
    availability: "low_stock",
    tags: ["High Protein", "Plant Based"],
    imageUrl: null,
    imageAlt: "Deep red kidney beans from Himalayan terraces",
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
    seo: {
      title: "Himalayan Red Rajma — Uttarkashi terraces",
      description: "Certified organic red rajma grown at altitude by Himgiri Terraces.",
      canonicalPath: "/product/himalayan-red-rajma",
      indexing: "index",
    },
  },
];

const categoryProducts: Record<string, string[]> = {
  "fresh-fruits": ["organic-alphonso-mangoes"],
  "organic-vegetables": ["organic-baby-spinach"],
  "grains-and-millets": ["sprouted-ragi-flour", "himalayan-red-rajma"],
  "cold-pressed-oils": ["wood-pressed-groundnut-oil"],
};

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
};

export function getCategoryPage(slug: string): PublicCategoryPage | null {
  const category = categories.find((entry) => entry.slug === slug);
  const hero = categoryHeroes[slug];
  if (!category || !hero) return null;
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
    hero: { ...hero, seasonLabel: category.seasonLabel, imageUrl: null, imageAlt: category.name },
    subcategories: [],
    products: products.filter((product) => slugs.includes(product.slug)),
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
    body: [
      "For most of the twentieth century, millets fed India. Then subsidised rice and wheat pushed them to the margins — hardy grains recast as poor man's food, grown on the land nobody irrigated.",
      "That story is reversing. Millets need a fraction of the water that rice demands, tolerate heat that wilts wheat, and grow on soil still recovering from decades of intensive farming. For collectives like Anandvan in Wardha, they are not nostalgia — they are the only crop that makes agronomic sense on regenerating land.",
      "The revival is also a flavour story. Sprouted ragi has a sweetness that refined flour never had. Little millet cooks into a pilaf with real bite. A generation of cooks is rediscovering grains their grandmothers never abandoned.",
      "What the movement needs now is steady demand: buyers who return every month, not just when a headline celebrates ancient grains. That steadiness is what lets a farmer plant a rain-fed crop with confidence.",
    ],
    pullQuote:
      "Millets are not nostalgia — they are the only crop that makes sense on regenerating land.",
    seo: {
      title: "The quiet revival of Indian millets — True Grit journal",
      description:
        "How a generation of farmers is bringing climate-resilient grains back to the Indian table.",
      canonicalPath: "/journal/quiet-revival-of-indian-millets",
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
  slug: category.slug,
  parentName: null,
  productCount: category.productCount,
  visibility: "public",
  status: "published",
  updatedAt: "2026-07-01T00:00:00Z",
}));

export const adminInventory: AdminInventoryRow[] = [
  {
    variantId: "var_alphonso_1kg",
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
