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
  keywords?: string | null;
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

export type CategoryTheme = "forest" | "sage" | "terracotta" | "charcoal" | "gold";

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
  imageUrl: string | null;
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
  returnEligible: boolean;
  seo: SeoDocument;
}

export interface CategorySummary {
  id: string;
  name: string;
  slug: string;
  shortDescription: string;
  themeKey: CategoryTheme;
  seasonLabel: string | null;
  imageUrl: string | null;
  productCount: number;
  /** Owning department, or `null` for a department (a root category). */
  parentId: string | null;
  /** Depth in the category tree: `0` for departments, `1` for subcategories. */
  level: number;
}

/** A department with its subcategories resolved — the shape the shop sidebar
 * and department rail consume. Built from the flat `CategorySummary[]` the
 * public API returns, so grouping costs no extra request. */
export interface CategoryTreeNode {
  department: CategorySummary;
  children: CategorySummary[];
  /**
   * Products reachable through this department, without double counting.
   *
   * The catalogue assigns a product to both its section and its owning
   * department (`is_primary` distinguishes them), so a department's own
   * `productCount` already covers its subcategories. Categories whose products
   * are only assigned at the leaf would report 0 on the department, so this is
   * the larger of the department's own count and its children's sum — correct
   * under either assignment style, and never inflated by the overlap.
   */
  totalProductCount: number;
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
    imageUrl: string | null;
    imageAlt: string | null;
  };
  subcategories: CategorySummary[];
  products: ProductSummary[];
  productsTotal: number;
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
  /** Banner image shown on the recipe page and as the listing thumbnail. */
  heroImageUrl?: string | null;
  heroImageAlt?: string | null;
}

export interface RecipeDetail extends RecipeSummary {
  ingredients: RecipeIngredient[];
  /** Optional intro/story section, rendered before the ingredients and steps. */
  blocks: ContentBlock[];
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
  /** Banner image shown on the article page and as the listing thumbnail. */
  heroImageUrl?: string | null;
  heroImageAlt?: string | null;
}

export interface ArticleDetail extends ArticleSummary {
  blocks: ContentBlock[];
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
    imageUrl?: string;
    imageAlt?: string;
    slides?: Array<{
      imageUrl: string;
      imageAlt: string;
      href: string;
      label: string;
      enabled?: boolean;
    }>;
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

/**
 * The block subset allowed inside article/recipe body content — a hero and a
 * newsletter signup don't make sense mid-article, so only these four appear
 * there. `rich_text` paragraphs may contain the inline link syntax
 * `[label](href)`; `product_collection` is how a post "highlights" products.
 */
export type ContentBlock = RichTextBlock | ProductCollectionBlock | FarmerStoryBlock | FaqBlock;

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
  slug: string;
  imageUrl: string;
  imageAlt: string;
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
  imageUrl: string;
  imageAlt: string;
  slug: string;
  parentName: string | null;
  productCount: number;
  visibility: "public" | "hidden" | "private";
  status: EntityStatus;
  updatedAt: string;
}

/** Geo release fields present on the category detail (not the list row) —
 * the same shape a product's release scope already uses. */
export interface CategoryReleaseFields {
  releaseScope: "global" | "selected";
  releaseCountries: string[];
}

export interface AdminInventoryRow {
  variantId: string;
  productId: string;
  productStatus: "draft" | "published" | "unpublished" | "archived";
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

// ---------------------------------------------------------------------------
// Admin content authoring: articles (blog), recipes — blogger/chef roles
// ---------------------------------------------------------------------------

export interface AdminArticleRow {
  id: string;
  title: string;
  slug: string;
  status: EntityStatus;
  authorName: string;
  updatedAt: string;
  publishedAt: string | null;
  /** True when a newer, unpublished draft version exists past the live one. */
  hasDraftChanges: boolean;
}

export interface AdminArticleDetail {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  readingMinutes: number;
  status: EntityStatus;
  authorUserId: string | null;
  heroMediaId: string | null;
  heroImageUrl: string;
  heroImageAlt: string;
  seoTitle: string;
  seoDescription: string;
  seoKeywords: string;
  canonicalUrl: string;
  indexingPolicy: "index" | "noindex";
  updatedAt: string;
  blocks: ContentBlock[];
  pullQuote: string | null;
}

export interface AdminRecipeRow {
  id: string;
  title: string;
  slug: string;
  status: EntityStatus;
  chefName: string;
  updatedAt: string;
  publishedAt: string | null;
  hasDraftChanges: boolean;
}

export interface AdminRecipeIngredient {
  id: string;
  label: string;
  quantityText: string;
  productId: string | null;
  productSlug: string | null;
}

export interface AdminRecipeDetail {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  prepMinutes: number;
  cookMinutes: number;
  servings: number;
  dietaryTags: string[];
  status: EntityStatus;
  chefUserId: string | null;
  heroImageUrl: string;
  heroImageAlt: string;
  seoTitle: string;
  seoDescription: string;
  seoKeywords: string;
  canonicalUrl: string;
  indexingPolicy: "index" | "noindex";
  updatedAt: string;
  blocks: ContentBlock[];
  steps: string[];
  ingredients: AdminRecipeIngredient[];
}

// ---------------------------------------------------------------------------
// Return requests (RMA)
// ---------------------------------------------------------------------------

export type ReturnReasonCode =
  "damaged" | "wrong_item" | "quality_issue" | "not_as_described" | "missing_item" | "other";

export type ReturnStatus =
  | "requested"
  | "under_review"
  | "approved"
  | "rejected"
  | "refunded"
  | "replaced"
  | "completed"
  | "cancelled";

export type ReturnResolutionType = "refund" | "replacement" | "store_credit" | "none";

export interface ReturnRequestSummary {
  id: string;
  orderReference: string;
  reasonCode: ReturnReasonCode;
  status: ReturnStatus;
  resolutionType: ReturnResolutionType | null;
  requestedAt: string;
  resolvedAt: string | null;
}

export interface AdminReturnRequestRow {
  id: string;
  orderReference: string;
  customerName: string;
  reasonCode: ReturnReasonCode;
  status: ReturnStatus;
  requestedRefundAmountMinor: number | null;
  resolutionType: ReturnResolutionType | null;
  resolutionAmountMinor: number | null;
  requestedAt: string;
  resolvedAt: string | null;
}

export interface AdminReturnRequestDetail {
  id: string;
  orderReference: string;
  orderTotalMinor: number;
  currencyCode: string;
  customerName: string;
  productName: string | null;
  variantName: string | null;
  reasonCode: ReturnReasonCode;
  description: string;
  evidenceMediaIds: string[];
  status: ReturnStatus;
  requestedRefundAmountMinor: number | null;
  resolutionType: ReturnResolutionType | null;
  resolutionAmountMinor: number | null;
  resolutionNotes: string | null;
  requestedAt: string;
  resolvedAt: string | null;
}

// ---------------------------------------------------------------------------
// Community blog/recipe submissions
// ---------------------------------------------------------------------------

export type SubmissionContentType = "article" | "recipe";

export type SubmissionStatus =
  "submitted" | "under_review" | "changes_requested" | "approved" | "rejected";

export interface SubmissionIngredient {
  label: string;
  quantityText: string;
}

export interface AdminSubmissionRow {
  id: string;
  contentType: SubmissionContentType;
  status: SubmissionStatus;
  title: string;
  contactName: string;
  contactEmail: string;
  contactPhone: string | null;
  createdAt: string;
  updatedAt: string;
  reviewedAt: string | null;
}

export interface AdminSubmissionDetail extends AdminSubmissionRow {
  excerpt: string | null;
  body: string;
  prepMinutes: number | null;
  cookMinutes: number | null;
  servings: number | null;
  dietaryTags: string[];
  ingredients: SubmissionIngredient[];
  steps: string[];
  reviewerNotes: string | null;
  publishedArticleId: string | null;
  publishedRecipeId: string | null;
}

// ---------------------------------------------------------------------------
// Community discussions
// ---------------------------------------------------------------------------

export type DiscussionStatus = "visible" | "hidden" | "archived" | "removed";
export type DiscussionCommentStatus = "visible" | "hidden" | "removed";

export interface AdminDiscussionRow {
  id: string;
  title: string;
  status: DiscussionStatus;
  authorName: string;
  commentCount: number;
  lastActivityAt: string;
  createdAt: string;
}

export interface AdminDiscussionComment {
  id: string;
  body: string;
  status: DiscussionCommentStatus;
  authorName: string;
  createdAt: string;
  moderationReason: string | null;
}

export interface AdminDiscussionDetail {
  id: string;
  title: string;
  body: string;
  status: DiscussionStatus;
  authorName: string;
  authorEmail: string;
  commentCount: number;
  lastActivityAt: string;
  createdAt: string;
  moderationReason: string | null;
  comments: AdminDiscussionComment[];
}

export interface CommunitySettings {
  minAccountAgeMonths: number;
}

// ---------------------------------------------------------------------------
// Route SEO overrides (routes with no single-segment CMS page record)
// ---------------------------------------------------------------------------

export interface AdminRouteSeo {
  path: string;
  seoTitle: string | null;
  seoDescription: string | null;
  seoKeywords: string | null;
  indexingPolicy: "index" | "noindex";
  updatedAt: string | null;
}

// ---------------------------------------------------------------------------
// Media library
// ---------------------------------------------------------------------------

export interface AdminMediaAssetRow {
  id: string;
  url: string;
  originalFilename: string;
  mimeType: string;
  sizeBytes: number;
  widthPx: number | null;
  heightPx: number | null;
  altText: string;
  caption: string;
  createdAt: string;
}

// ---------------------------------------------------------------------------
// Owner reports console (curated, parameterized, read-only)
// ---------------------------------------------------------------------------

export interface ReportParamDefinition {
  key: string;
  label: string;
  kind: "date" | "country";
  required: boolean;
}

export interface ReportDefinitionSummary {
  id: string;
  label: string;
  description: string;
  params: ReportParamDefinition[];
}

export interface ReportRunResult {
  id: string;
  label: string;
  columns: string[];
  rows: Array<Array<string | number | null>>;
}

// ---------------------------------------------------------------------------
// Owner-only: server logs and read-only DB browser
// ---------------------------------------------------------------------------

export interface AdminServerLogRow {
  id: string;
  level: string;
  event: string;
  fields: Record<string, unknown>;
  createdAt: string;
}

export interface AdminDbBrowserTableData {
  columns: string[];
  rows: Array<Array<string | number | null>>;
  limit: number;
  offset: number;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    requestId: string;
  };
}
