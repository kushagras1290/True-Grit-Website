/**
 * Public API contracts for the True Grit platform.
 *
 * These types mirror the Pydantic response schemas in `apps/api` at the public
 * boundary (camelCase JSON, UTC ISO 8601 timestamps, integer minor-unit money).
 * When the FastAPI OpenAPI document is wired into CI, generated types should
 * replace the hand-maintained entries here — keep the shapes identical.
 */

// ---------------------------------------------------------------------------
// Money
// ---------------------------------------------------------------------------

export interface Money {
  amountMinor: number;
  currencyCode: string;
}

/** Format integer minor units (paise) as a display price, e.g. 89900 -> "₹899". */
export function formatMoney(amountMinor: number, currencyCode = "INR", locale = "en-IN"): string {
  if (!Number.isInteger(amountMinor) || amountMinor < 0) {
    throw new RangeError(`amountMinor must be a non-negative integer, got ${amountMinor}`);
  }
  const major = amountMinor / 100;
  const hasPaise = amountMinor % 100 !== 0;
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: currencyCode,
    minimumFractionDigits: hasPaise ? 2 : 0,
    maximumFractionDigits: hasPaise ? 2 : 0,
  }).format(major);
}

// ---------------------------------------------------------------------------
// SEO and navigation
// ---------------------------------------------------------------------------

export interface SeoDocument {
  title: string;
  description: string;
  canonicalPath: string;
  indexing: "index" | "noindex";
}

export interface BreadcrumbItem {
  label: string;
  path: string;
}

export interface NavigationItem {
  label: string;
  path: string;
}

export interface PublicBootstrap {
  navigation: NavigationItem[];
  footerNavigation: NavigationItem[];
  announcement: { message: string; path: string | null } | null;
}

// ---------------------------------------------------------------------------
// Catalogue
// ---------------------------------------------------------------------------

export type ProductAvailability = "in_stock" | "low_stock" | "out_of_stock";

export type CategoryTheme = "forest" | "sage" | "terracotta" | "charcoal";

export interface ProductSummary {
  id: string;
  name: string;
  slug: string;
  farmName: string;
  region: string;
  certification: string;
  priceMinor: number;
  saleMinor: number | null;
  currencyCode: string;
  unitLabel: string;
  availability: ProductAvailability;
  tags: string[];
  imageAlt: string;
}

export interface VariantSummary {
  id: string;
  name: string;
  sku: string;
  listMinor: number;
  saleMinor: number | null;
  availability: ProductAvailability;
}

export interface TraceabilityStep {
  label: string;
  detail: string;
}

export interface ProductDetail extends ProductSummary {
  shortDescription: string;
  overview: string;
  farmSlug: string;
  storageGuidance: string;
  harvestNote: string;
  growingMethod: string;
  variants: VariantSummary[];
  traceability: TraceabilityStep[];
  relatedSlugs: string[];
  seo: SeoDocument;
}

export interface CategorySummary {
  id: string;
  name: string;
  slug: string;
  shortDescription: string;
  themeKey: CategoryTheme;
  seasonLabel: string | null;
  productCount: number;
}

export interface FaqItem {
  question: string;
  answer: string;
}

export interface PublicCategoryPage {
  id: string;
  name: string;
  slug: string;
  breadcrumbs: BreadcrumbItem[];
  themeKey: CategoryTheme;
  hero: {
    eyebrow: string;
    title: string;
    description: string;
    seasonLabel: string | null;
  };
  subcategories: CategorySummary[];
  products: ProductSummary[];
  faq: FaqItem[];
  seo: SeoDocument;
  updatedAt: string;
}

// ---------------------------------------------------------------------------
// Farms, recipes, journal
// ---------------------------------------------------------------------------

export interface FarmSummary {
  id: string;
  name: string;
  slug: string;
  farmerName: string;
  region: string;
  summary: string;
  certification: string;
  establishedYear: number;
}

export interface FarmDetail extends FarmSummary {
  story: string;
  methods: string[];
  productSlugs: string[];
  seo: SeoDocument;
}

export interface RecipeIngredient {
  label: string;
  quantityText: string;
  productSlug: string | null;
}

export interface RecipeSummary {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  prepMinutes: number;
  cookMinutes: number;
  servings: number;
  dietaryTags: string[];
}

export interface RecipeDetail extends RecipeSummary {
  ingredients: RecipeIngredient[];
  steps: string[];
  seo: SeoDocument;
}

export interface ArticleSummary {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  authorName: string;
  publishedAt: string;
  readingMinutes: number;
}

export interface ArticleDetail extends ArticleSummary {
  body: string[];
  pullQuote: string | null;
  seo: SeoDocument;
}

// ---------------------------------------------------------------------------
// CMS blocks (discriminated union — render only known types)
// ---------------------------------------------------------------------------

export interface BlockBase {
  id: string;
  version: number;
  enabled: boolean;
}

export interface HeroBlock extends BlockBase {
  type: "hero";
  props: {
    layout: "editorial-split" | "full-bleed";
    eyebrow: string;
    heading: string;
    text: string;
    primaryAction: { label: string; href: string };
    secondaryAction: { label: string; href: string } | null;
  };
}

export interface CategoryCollectionBlock extends BlockBase {
  type: "category_collection";
  props: { heading: string; categorySlugs: string[] };
}

export interface ProductCollectionBlock extends BlockBase {
  type: "product_collection";
  props: {
    heading: string;
    source: "manual" | "rule";
    productSlugs: string[];
    limit: number;
  };
}

export interface FarmerStoryBlock extends BlockBase {
  type: "farmer_story";
  props: { farmSlug: string; quote: string; attribution: string };
}

export interface FaqBlock extends BlockBase {
  type: "faq";
  props: { heading: string; items: FaqItem[] };
}

export interface RichTextBlock extends BlockBase {
  type: "rich_text";
  props: { paragraphs: string[] };
}

export interface NewsletterBlock extends BlockBase {
  type: "newsletter";
  props: { heading: string; consentText: string };
}

export type PublicPageBlock =
  | HeroBlock
  | CategoryCollectionBlock
  | ProductCollectionBlock
  | FarmerStoryBlock
  | FaqBlock
  | RichTextBlock
  | NewsletterBlock;

export type PublicBlockType = PublicPageBlock["type"];

export interface PublicPage {
  id: string;
  slug: string;
  title: string;
  blocks: PublicPageBlock[];
  seo: SeoDocument;
}

// ---------------------------------------------------------------------------
// Admin DTOs (subset used by the admin SPA)
// ---------------------------------------------------------------------------

export type WorkflowState =
  "draft" | "in_review" | "changes_requested" | "approved" | "scheduled" | "published";

export type EntityStatus =
  | "draft"
  | "in_review"
  | "approved"
  | "scheduled"
  | "published"
  | "unpublished"
  | "discontinued"
  | "archived";

export interface AdminProductRow {
  id: string;
  name: string;
  sku: string;
  status: EntityStatus;
  categories: string[];
  farmName: string;
  priceRange: string;
  availableStock: number;
  updatedAt: string;
  updatedBy: string;
}

export interface AdminCategoryRow {
  id: string;
  name: string;
  slug: string;
  parentName: string | null;
  productCount: number;
  visibility: "public" | "hidden" | "private";
  status: EntityStatus;
  updatedAt: string;
}

export interface AdminInventoryRow {
  variantId: string;
  productName: string;
  variantName: string;
  sku: string;
  locationName: string;
  onHand: number;
  reserved: number;
  reorderThreshold: number;
  updatedAt: string;
}

export interface AdminOrderRow {
  id: string;
  publicReference: string;
  customerEmail: string;
  totalMinor: number;
  currencyCode: string;
  orderStatus: string;
  paymentStatus: string;
  fulfilmentStatus: string;
  placedAt: string;
}

export interface AdminUserRow {
  id: string;
  displayName: string;
  email: string;
  status: "invited" | "active" | "disabled";
  roles: string[];
  roleIds?: string[];
  lastSignInAt: string | null;
}

export interface AuditLogRow {
  id: string;
  actorName: string;
  action: string;
  entityType: string;
  entityId: string;
  requestId: string;
  createdAt: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    requestId: string;
  };
}
