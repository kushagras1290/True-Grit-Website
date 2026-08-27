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

/** Whether a product's orderability follows the site-wide payments switch,
 *  or overrides it (migration 0069) in either direction. */
export type PaymentsOverride = "inherit" | "force_enabled" | "force_disabled";

export type CategoryTheme = "forest" | "sage" | "terracotta" | "charcoal" | "gold";

export interface ProductSummary {
  id: string;
  name: string;
  slug: string;
  farmName: string;
  region: string;
  certifications: string[];
  priceMinor: number;
  saleMinor: number | null;
  /** Set only when an active price-adjustment rule changes what this visitor
   *  pays (`services/price_adjustments.py`) -- null, not zero, so "no
   *  adjustment" is distinguishable from "adjusted to no change". Below
   *  `priceMinor` is a genuine discount (show `priceMinor` struck through);
   *  above it is a genuine markup (show only `adjustedMinor`, never a fake
   *  "was" price for it). */
  adjustedMinor: number | null;
  currencyCode: string;
  unitLabel: string;
  availability: ProductAvailability;
  tags: string[];
  imageUrl: string | null;
  imageAlt: string;
  /** Per-product order/payment switch (migration 0048), independent of the
   *  site-wide one on Site Control. False means the product is still shown
   *  and browsable -- just not currently orderable. */
  acceptsOrders: boolean;
  /** Overrides the site-wide payments switch for this one product, in either
   *  direction (migration 0069) -- see `PaymentsOverride`. Combine with the
   *  site-wide `payments.enabled` flag (`useSiteSettings`) to decide whether
   *  "Add to basket" renders: enabled when `paymentsOverride === "inherit"`
   *  follows the site-wide flag, `"force_enabled"` always allows it,
   *  `"force_disabled"` never does. */
  paymentsOverride: PaymentsOverride;
  /** The variant `priceMinor`/`saleMinor`/`adjustedMinor`/`unitLabel` above
   *  already describe. Enough to add a single-variant product to the cart
   *  straight from a batched summary fetch (`?slugs=a,b,c`) -- no separate
   *  per-slug detail request needed just to learn the variant id. Null only
   *  for a product with no active variant at all. */
  leadVariantId: string | null;
  /** Average of *approved* reviews only (migration 0057); 0 for a product with
   *  none yet, not undefined -- "no ratings" is its own display state, not a
   *  missing-data case. */
  ratingAverage: number;
  ratingCount: number;
  /** Gallery images available to listing cards for hover slideshows and to
   *  detail pages for the full viewer. Includes whatever the admin saved in
   *  product image order; empty when no gallery has been configured. */
  images?: ProductImage[];
}

export interface VariantSummary {
  id: string;
  name: string;
  sku: string;
  listMinor: number;
  saleMinor: number | null;
  adjustedMinor: number | null;
  availability: ProductAvailability;
}

export interface TraceabilityStep {
  label: string;
  detail: string;
}

/** A product gallery photo, ordered by the admin. */
export interface ProductImage {
  id: string;
  imageUrl: string;
  imageAlt: string | null;
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
  /** Gallery photos beyond `imageUrl` above. Optional (rather than always an
   *  array) so hand-written fixtures and any older cached response need not
   *  carry an empty array just to satisfy the type -- absent reads exactly
   *  like empty everywhere this is consumed. */
  images?: ProductImage[];
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

/** One selectable option in the shop grid's dietary filter — `key` is the
 * `tags.key` value (`?diet=` query param), `label` the checkbox text. */
export interface DietTagOption {
  key: string;
  label: string;
}

/** One selectable option in the shop grid's certification filter — `slug` is
 * the `certifications.slug` value (`?certification=` query param). */
export interface CertificationOption {
  slug: string;
  name: string;
}

/** The full vocabulary behind the shop grid's dietary/certification filter
 * checkboxes (`GET /v1/public/filters`) — every option, not just ones
 * currently assigned to a published product. */
export interface ProductFilters {
  dietTags: DietTagOption[];
  certifications: CertificationOption[];
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
  /** The individual farm page's own banner (distinct from the sitewide
   *  `/farms` listing banner in `StorefrontSettings.banners`). `null` renders
   *  `PageBanner`'s plain gradient backdrop, not a missing-image error. */
  heroImageUrl: string | null;
  heroImageAlt: string | null;
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
  /** Schema.org `recipeCuisine`. Null means the recipe makes no claim, and the
   *  structured data omits the field rather than guessing one. */
  cuisine?: string | null;
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
  /** `heading` is optional: a block used purely as a continuation paragraph
   *  (no new subheading) omits it. */
  props: { heading?: string; paragraphs: string[] };
}

export interface BulletListBlock extends BlockBase {
  type: "bullet_list";
  /** Same inline `[label](href)` link syntax as `rich_text`, one link per
   *  item at most in practice, so a bullet can point at a product or a
   *  community discussion without breaking out of list rhythm. */
  props: { heading?: string; items: string[] };
}

export interface NewsletterBlock extends BlockBase {
  type: "newsletter";
  props: { heading: string; consentText: string };
}

/**
 * One card in a `page_links` block: a short, human-written snippet describing
 * another storefront page. `enabled` hides a single card without deleting the
 * copy, the same way a hero slide is parked rather than thrown away.
 */
export interface PageLinkItem {
  label: string;
  description: string;
  href: string;
  enabled: boolean;
}

/**
 * A directory of the rest of the site, rendered as small snippet cards. The
 * homepage carries one so a first-time customer can see what else exists
 * without hunting through the header menu.
 */
export interface PageLinksBlock extends BlockBase {
  type: "page_links";
  props: { heading: string; intro: string; items: PageLinkItem[] };
}

/**
 * "What customers are saying". `source: "rule"` resolves live to the current
 * top-rated approved reviews sitewide (`minRating` and up); `source: "manual"`
 * shows exactly the reviews in `reviewIds`, in that order. Ships enabled by
 * default (migration 0057) in rule mode, so it renders nothing until real
 * reviews exist rather than needing an editor to remember to turn it on.
 */
export interface ReviewsShowcaseBlock extends BlockBase {
  type: "reviews_showcase";
  props: {
    heading: string;
    subheading: string;
    source: "manual" | "rule";
    reviewIds: string[];
    limit: number;
    minRating: number;
  };
}

/**
 * "What's on offer" -- the same live-resolved two-mode split as
 * `reviews_showcase`. `source: "manual"` pins one specific `promotionId`;
 * `source: "rule"` resolves the current highest-priority automatic
 * promotion. No heading/subheading here: a promotion already carries its own
 * `headline`/`description` (migration 0060), which is also what the
 * checkout-page callout reads, so the homepage and checkout never show two
 * hand-maintained versions of the same offer.
 */
export interface PromotionBannerBlock extends BlockBase {
  type: "promotion_banner";
  props: {
    source: "manual" | "rule";
    promotionId: string | null;
  };
}

/**
 * Real bestsellers -- ranked by quantity actually sold, resolved live on
 * every render (like `product_collection`'s rule mode), never a curated
 * list. Renders nothing when there is no order history yet, the same
 * empty-is-legitimate contract every rule-driven block already follows.
 */
export interface RecommendationsBlock extends BlockBase {
  type: "recommendations";
  props: {
    heading: string;
    subheading: string;
    limit: number;
  };
}

/**
 * A single full-width graphic -- a brand statement or campaign lockup that is
 * itself the content, unlike `hero`'s rotating carousel or `rich_text`'s
 * prose. Optionally links somewhere; renders as a plain image when it does
 * not.
 */
export interface ImageBannerBlock extends BlockBase {
  type: "image_banner";
  props: {
    imageUrl: string;
    imageAlt: string;
    href: string | null;
  };
}

export type PublicPageBlock =
  | HeroBlock
  | CategoryCollectionBlock
  | ProductCollectionBlock
  | FarmerStoryBlock
  | FaqBlock
  | RichTextBlock
  | BulletListBlock
  | NewsletterBlock
  | PageLinksBlock
  | ReviewsShowcaseBlock
  | PromotionBannerBlock
  | RecommendationsBlock
  | ImageBannerBlock;

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
export type ContentBlock =
  RichTextBlock | BulletListBlock | ProductCollectionBlock | FarmerStoryBlock | FaqBlock;

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

/** One product with all of its variants' stock levels together -- the
 *  inventory page's unit of pagination and display, matching the Products
 *  page (one row per product, alphabetical) rather than repeating the
 *  product name on a separate row per variant. */
export interface AdminInventoryProductGroup {
  productId: string;
  productName: string;
  productStatus: "draft" | "published" | "unpublished" | "archived";
  variants: AdminInventoryRow[];
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
  agentRiskScore: number | null;
  agentDecision: RefundOrchestratorDecision | null;
}

export interface RefundOrchestratorSignal {
  id: string;
  label: string;
  weight: number;
  rationale: string;
}

export type RefundOrchestratorDecision = "auto_approve" | "escalate" | "auto_deny";

export interface RefundOrchestratorAssessment {
  riskScore: number;
  decision: RefundOrchestratorDecision;
  signals: RefundOrchestratorSignal[];
  rationale: string;
  evaluatedAt: string;
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
  resolvedByAgent: boolean;
  agentAssessment: RefundOrchestratorAssessment | null;
}

// ---------------------------------------------------------------------------
// Product reviews and ratings (migration 0005, extended by 0057)
// ---------------------------------------------------------------------------

export type ReviewStatus = "pending" | "approved" | "rejected" | "removed";

/** One approved review as shown on a product page. */
export interface ProductReview {
  id: string;
  rating: number;
  title: string | null;
  body: string;
  authorName: string;
  /** True when the review is tied to a real order (every review is, in
   *  practice -- `services.reviews.create_review` requires one -- but the
   *  field stays boolean rather than assumed so the storefront never has to
   *  guess at a row it did not create). */
  verifiedPurchase: boolean;
  createdAt: string;
}

/** A review on the homepage's `reviews_showcase` feed, which spans every
 *  product -- so unlike `ProductReview` it carries the product it is about. */
export interface FeaturedReview extends ProductReview {
  productName: string;
  productSlug: string;
}

/** A review the calling customer wrote, as shown on their own order page --
 *  carries `status` so "pending moderation" reads differently from
 *  "published". */
export interface MyReview {
  id: string;
  productId: string;
  productName: string;
  productSlug: string;
  rating: number;
  title: string | null;
  body: string;
  status: ReviewStatus;
  createdAt: string;
}

export interface AdminReviewRow {
  id: string;
  productName: string;
  productSlug: string;
  rating: number;
  title: string | null;
  body: string;
  status: ReviewStatus;
  authorName: string;
  authorEmail: string | null;
  createdAt: string;
  moderatedAt: string | null;
  moderationReason: string | null;
}

// ---------------------------------------------------------------------------
// Coupons and promotions (migration 0005, extended by 0060). A promotion with
// no coupons is automatic -- it applies to every eligible cart with no code.
// One or more coupons make it code-gated.
// ---------------------------------------------------------------------------

export type PromotionStatus = "draft" | "scheduled" | "active" | "paused" | "ended" | "archived";

export type PromotionStackingPolicy = "exclusive" | "stackable";

export type PromotionActionType = "percentage_discount" | "fixed_discount" | "free_delivery";

/** The one promotion to advertise right now -- the same shape the homepage
 *  banner and the checkout box both read, so they always show identical
 *  copy. `code` is only present when the promotion is code-gated (has at
 *  least one active coupon); an automatic promotion has none to show. */
export interface FeaturedPromotion {
  id: string;
  name: string;
  headline: string;
  description: string | null;
  code: string | null;
}

export interface AdminPromotionRow {
  id: string;
  name: string;
  status: PromotionStatus;
  priority: number;
  startsAt: string | null;
  endsAt: string | null;
  stackingPolicy: PromotionStackingPolicy;
  usageLimitTotal: number | null;
  usageLimitPerCustomer: number | null;
  headline: string | null;
  description: string | null;
  couponCount: number;
  redemptionCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface AdminCouponRow {
  id: string;
  code: string;
  active: boolean;
  redemptionCount: number;
  createdAt: string;
}

export interface AdminPromotionAction {
  actionType: PromotionActionType;
  valueBasisPoints: number | null;
  amountMinor: number | null;
  maximumDiscountMinor: number | null;
}

export interface AdminPromotionDetail extends AdminPromotionRow {
  rule: { minSubtotalMinor: number | null } | null;
  action: AdminPromotionAction | null;
  coupons: AdminCouponRow[];
}

// ---------------------------------------------------------------------------
// Bundles -- curated sets of specific variants sold together at a flat price
// ---------------------------------------------------------------------------

export type BundleStatus = "draft" | "active" | "ended" | "archived";

export interface AdminBundleRow {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  status: BundleStatus;
  bundlePriceMinor: number;
  imageUrl: string | null;
  imageAlt: string | null;
  itemCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface AdminBundleItem {
  id: string;
  variantId: string;
  quantity: number;
  variantName: string;
  sku: string;
  productId: string;
  productName: string;
  productSlug: string;
  imageUrl: string | null;
  unitPriceMinor: number;
  lineTotalMinor: number;
}

export interface AdminBundleDetail extends AdminBundleRow {
  items: AdminBundleItem[];
}

/** A bundle item as the storefront reads it -- same shape as
 *  `AdminBundleItem` minus the admin row id (the public API has no reason to
 *  expose `bundle_items.id`). */
export interface PublicBundleItem {
  variantId: string;
  quantity: number;
  variantName: string;
  sku: string;
  productId: string;
  productName: string;
  productSlug: string;
  imageUrl: string | null;
  unitPriceMinor: number;
  lineTotalMinor: number;
}

/** An active, purchasable bundle -- `savingsMinor` is computed server-side
 *  against current variant prices, the same math `resolve_bundle_discount`
 *  applies at checkout, so the shop card can never advertise a number
 *  checkout would not also grant. */
export interface PublicBundle {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  bundlePriceMinor: number;
  componentSumMinor: number;
  savingsMinor: number;
  imageUrl: string | null;
  imageAlt: string | null;
  items: PublicBundleItem[];
}

// ---------------------------------------------------------------------------
// Delivery addresses -- reusable, unlike the ad-hoc address ordinary
// checkout takes on the request itself. Subscriptions are the only feature
// that needs one (a renewal has no request to take an address from).
// ---------------------------------------------------------------------------

export interface CustomerAddress {
  id: string;
  label: string | null;
  recipientName: string;
  phoneE164: string | null;
  line1: string;
  line2: string | null;
  city: string;
  state: string;
  postalCode: string;
  countryCode: string;
  isDefaultDelivery: boolean;
  createdAt: string;
}

// ---------------------------------------------------------------------------
// Subscriptions -- "Subscribe & Save" recurring cash-on-delivery deliveries
// of a single product variant. Off sitewide by default; see
// `StorefrontSettings.subscriptions` / `StorefrontSettingsEffective.subscriptions`.
// ---------------------------------------------------------------------------

export type SubscriptionFrequency = "weekly" | "biweekly" | "monthly";
export type SubscriptionStatus = "active" | "paused" | "cancelled";

/** The shape both the customer's own "My Subscriptions" list and the admin
 *  support view read -- the admin view additionally gets `customerName`/
 *  `customerEmail` populated (null for a customer reading their own). */
export interface SubscriptionRow {
  id: string;
  customerUserId: string;
  variantId: string;
  productId: string;
  productName: string;
  productSlug: string;
  variantName: string;
  sku: string;
  imageUrl: string | null;
  unitPriceMinor: number | null;
  quantity: number;
  frequency: SubscriptionFrequency;
  status: SubscriptionStatus;
  addressId: string;
  nextOrderDate: string;
  lastOrderId: string | null;
  createdAt: string;
  updatedAt: string;
  cancelledAt: string | null;
  customerName: string | null;
  customerEmail: string | null;
}

// ---------------------------------------------------------------------------
// Wishlist -- a signed-in customer saving a product for later. Product-level
// (one wishlist entry per product, not per variant) to match the storefront's
// product-card UI. No status machine, no financial commitment -- the
// simplest customer-owned resource in the contract, deliberately smaller
// than SubscriptionRow above. `variantId`/`variantName`/`sku`/`unitPriceMinor`
// describe the product's first active variant, for display only -- adding
// the saved product to cart still goes through the normal variant picker.
// ---------------------------------------------------------------------------

export interface WishlistItem {
  productId: string;
  productName: string;
  productSlug: string;
  imageUrl: string | null;
  variantId: string | null;
  variantName: string | null;
  sku: string | null;
  unitPriceMinor: number | null;
  currencyCode: string | null;
  addedAt: string;
}

// ---------------------------------------------------------------------------
// Analytics -- a visual dashboard over a date range, computed live from
// orders/order_items. Distinct from the Owner Reports library (curated
// named queries, no charts): this is "how is the store doing".
// ---------------------------------------------------------------------------

export interface AnalyticsRevenuePoint {
  date: string;
  revenueMinor: number;
  orderCount: number;
}

export interface AnalyticsTopProduct {
  productId: string;
  productName: string;
  unitsSold: number;
  revenueMinor: number;
}

export interface AnalyticsStatusCount {
  status: string;
  orderCount: number;
}

export interface AnalyticsOverview {
  fromDate: string;
  toDate: string;
  revenueMinor: number;
  orderCount: number;
  averageOrderValueMinor: number;
  newCustomers: number;
  revenueByDay: AnalyticsRevenuePoint[];
  topProducts: AnalyticsTopProduct[];
  statusBreakdown: AnalyticsStatusCount[];
  recommendations: RecommendationAnalytics;
}

export interface RecommendationAnalytics {
  impressions: number;
  clicks: number;
  addToCarts: number;
  clickThroughRate: number;
  attributedOrders: number;
  attributedUnits: number;
  attributedRevenueMinor: number;
}

export interface RecommendationSignal {
  runId: string | null;
  sourceProductId: string;
  score: number;
  confidence: number;
  lift: number;
  cosineSimilarity: number;
  reason: "frequently_bought_together" | "similar_product" | "trending";
}

export interface RecommendedProduct {
  product: ProductSummary;
  recommendation: RecommendationSignal;
}

export interface DemandForecastPoint {
  forecastDate: string;
  predictedUnits: number;
  lowerUnits: number;
  upperUnits: number;
  seasonalityMultiplier: number;
}

export interface InventoryIntelligenceItem {
  productId: string;
  productName: string;
  productStatus: string;
  variantId: string;
  variantName: string;
  sku: string;
  availableUnits: number;
  avgDaily7: number;
  avgDaily30: number;
  leadTimeDays: number;
  safetyStockDays: number;
  daysUntilStockout: number | null;
  projectedStockoutDate: string | null;
  reorderRecommended: boolean;
  recommendedOrderUnits: number;
  dataDays: number;
}

export interface InventoryIntelligenceResponse {
  run: {
    id: string;
    modelVersion: string;
    horizonDays: number;
    completedAt: string;
  } | null;
  summary: { reorderSoon: number; forecastedSkus: number };
  items: InventoryIntelligenceItem[];
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
  indexingPolicy: "index" | "noindex";
  comments: AdminDiscussionComment[];
}

export interface CommunitySettings {
  minAccountAgeMonths: number;
}

// ---------------------------------------------------------------------------
// Reader comments on published articles/recipes (migration 0043)
// ---------------------------------------------------------------------------

export type ContentCommentContentType = "article" | "recipe";
export type ContentCommentStatus = "visible" | "hidden" | "removed";

export interface AdminContentCommentRow {
  id: string;
  contentType: ContentCommentContentType;
  body: string;
  status: ContentCommentStatus;
  createdAt: string;
  moderatedAt: string | null;
  moderationReason: string | null;
  authorName: string;
  /** Resolved through `contactable_email` server-side; null for a phone-only
   *  account rather than a placeholder address. */
  authorEmail: string | null;
  /** Title and slug of the article or recipe the comment is attached to, so
   *  a moderator can open the post without a second lookup. */
  parentTitle: string;
  parentSlug: string;
}

// ---------------------------------------------------------------------------
// Farm partnership applications (migration 0044) -- growers apply from the
// storefront to supply the marketplace; staff triage the pipeline here.
// Approval records a decision only; it does not create a `farms` row -- see
// the migration for why this is not modelled on content submissions.
// ---------------------------------------------------------------------------

export type FarmRequestStatus =
  "submitted" | "under_review" | "contacted" | "approved" | "rejected";

export interface AdminFarmRequestRow {
  id: string;
  status: FarmRequestStatus;
  farmName: string;
  region: string;
  state: string | null;
  city: string | null;
  contactName: string;
  contactEmail: string;
  contactPhone: string;
  createdAt: string;
  reviewedAt: string | null;
  linkedFarmId: string | null;
}

export interface AdminFarmRequestDetail extends AdminFarmRequestRow {
  pincode: string | null;
  establishedYear: number | null;
  landAreaAcres: string | null;
  certification: string | null;
  primaryProduce: string | null;
  farmingPractices: string | null;
  websiteUrl: string | null;
  message: string;
  reviewerNotes: string | null;
  reviewerName: string | null;
  submitterName: string | null;
  linkedFarmName: string | null;
  updatedAt: string;
}

// ---------------------------------------------------------------------------
// Storefront feature switches (app_settings, migration 0040)
//
// `settings` is what the owner chose; `effective` is what that resolves to once
// the API's own configuration is taken into account (no Google client id, no
// SMS key, no payment gateway). The console shows both: a ticked box whose
// effective value is false is a real state, and the operator needs to be told
// why rather than left wondering.
// ---------------------------------------------------------------------------

export interface StorefrontSettings {
  googleSignIn: boolean;
  facebookSignIn: boolean;
  phoneOtpSignIn: boolean;
  passwordSignIn: boolean;
  registration: boolean;
  payments: boolean;
  paymentsDisabledNotice: string;
  promotions: boolean;
  recommendations: boolean;
  subscriptions: boolean;
  dietCertFilters: boolean;
  giftCards: boolean;
  loyalty: boolean;
  pickup: boolean;
  preorders: boolean;
  deliveryZones: boolean;
  b2b: boolean;
  refundOrchestrator: boolean;
  englishOnly: boolean;
  blogBannerImageUrl: string;
  blogBannerImageAlt: string;
  farmsBannerImageUrl: string;
  farmsBannerImageAlt: string;
}

export interface StorefrontSettingsEffective {
  googleSignIn: boolean;
  facebookSignIn: boolean;
  phoneOtpSignIn: boolean;
  passwordSignIn: boolean;
  registration: boolean;
  payments: boolean;
  promotions: boolean;
  recommendations: boolean;
  subscriptions: boolean;
  dietCertFilters: boolean;
  giftCards: boolean;
  loyalty: boolean;
  pickup: boolean;
  preorders: boolean;
  deliveryZones: boolean;
  b2b: boolean;
  refundOrchestrator: boolean;
  englishOnly: boolean;
  anySignInAvailable: boolean;
}

export interface StorefrontSettingsResponse {
  settings: StorefrontSettings;
  effective: StorefrontSettingsEffective;
}

// ---------------------------------------------------------------------------
// Email admin console (`/email` page, `services/email_settings.py`,
// `services/email_gate.py`) -- provider selection, per-category on/off
// switches and rate limits, and recent send activity.
// ---------------------------------------------------------------------------

export type EmailProvider = "resend" | "brevo";

export interface EmailCategorySettings {
  label: string;
  description: string;
  enabled: boolean;
  hourlyLimit: number | null;
  dailyLimit: number | null;
}

export interface EmailControlSettings {
  provider: EmailProvider | null;
  categories: Record<string, EmailCategorySettings>;
  globalHourlyLimit: number;
  globalDailyLimit: number;
  configuredProviders: {
    resend: boolean;
    brevo: boolean;
    smtp: boolean;
  };
  activeProvider: string;
}

export interface EmailCategoryUpdate {
  enabled?: boolean;
  hourlyLimit?: number | null;
  dailyLimit?: number | null;
}

export interface EmailSettingsUpdate {
  provider?: EmailProvider | null;
  globalHourlyLimit?: number;
  globalDailyLimit?: number;
  categories?: Record<string, EmailCategoryUpdate>;
}

export type EmailOutcome = "sent" | "blocked_disabled" | "rate_limited" | "provider_error";

export interface EmailActivityRow {
  id: string;
  category: string;
  provider: string;
  outcome: EmailOutcome;
  detail: string;
  recipientDomain: string | null;
  occurredAt: string;
}

export interface EmailActivityResponse {
  entries: EmailActivityRow[];
  summary24h: Record<EmailOutcome, number>;
}

export interface EmailTestSendResult {
  sent: boolean;
  provider: string;
  to: string;
}

// ---------------------------------------------------------------------------
// Appearance: colour theme and ambient effects
// ---------------------------------------------------------------------------

/**
 * The storefront's colour roles, one per themeable CSS custom property.
 *
 * Semantic names, never raw palette names: an owner picks "the colour of a
 * card" rather than "ivory", so a re-theme cannot leave a token whose name
 * contradicts its value. Each key maps to a `--color-*` property declared in
 * `@truegrit/ui/tokens.css`.
 */
export const THEME_TOKEN_KEYS = [
  "bgCanvas",
  "bgSurface",
  "bgSubtle",
  "bgInverse",
  "bannerBackdrop",
  "textPrimary",
  "textSecondary",
  "textInverse",
  "brandPrimary",
  "brandAccent",
  "brandGold",
  "borderSubtle",
  "borderStrong",
  "danger",
  "success",
  "warning",
] as const;

export type ThemeTokenKey = (typeof THEME_TOKEN_KEYS)[number];

/**
 * A sparse set of colour overrides.
 *
 * Sparse on purpose: a missing (or empty) key means "keep the shipped default",
 * so a theme only ever carries what somebody deliberately changed. A partial or
 * truncated payload therefore degrades to the stock palette rather than to a
 * page of undefined colours.
 */
export type ThemeTokens = Partial<Record<ThemeTokenKey, string>>;

/**
 * The whole colour theme: one site-wide set plus per-path overrides.
 *
 * `pages` is keyed by storefront path (`/shop`, `/blog`). It ships in full on
 * the first response so client-side navigation re-themes instantly, with no
 * second request and no flash of the previous page's palette.
 */
export interface StorefrontTheme {
  global: ThemeTokens;
  pages: Record<string, ThemeTokens>;
}

/** Falling/drifting particle effects. `none` is the shipped default. */
export const AMBIENT_EFFECT_KEYS = [
  "none",
  "snow",
  "leaves",
  "petals",
  "rain",
  "fireflies",
  "bubbles",
  "confetti",
  "stars",
  "embers",
  "dust",
  "seeds",
  "hearts",
  "sparkles",
  "fog",
  "meteors",
  "stardust",
  "galaxySwirl",
  "nebulaClouds",
  "supernovaFlashes",
  "lightningFlashes",
  "hailstorm",
  "mistDrift",
  "windyLeaves",
  "thunderRain",
  "fairyDust",
  "enchantedGlow",
  "champagneBubbles",
  "floatingWisps",
  "glowingRunes",
  "driftingPollen",
  "autumnLeaves",
  "sakuraBloom",
  "dandelionSeeds",
  "mossSporeGlow",
  "confettiParty",
  "neonGlowSticks",
  "discoLights",
  "floatingBalloons",
  "partyStreamers",
  "auroraWaves",
  "frostSparkle",
  "cometTrail",
  "shootingStars",
  "cherryBlossom",
  "mapleLeavesFall",
  "goldenEmbers",
  "iceCrystals",
  "magicSparks",
  "oceanBubbles",
  "cosmicDust",
] as const;

export type AmbientEffectKey = (typeof AMBIENT_EFFECT_KEYS)[number];

/** Pointer trails. `none` leaves the cursor completely alone. */
export const CURSOR_TRAIL_KEYS = [
  "none",
  "dots",
  "ribbon",
  "comet",
  "sparkle",
  "bubbles",
  "stars",
  "hearts",
  "snow",
  "glow",
  "rings",
  "paint",
  "fireflies",
  "leaves",
  "petals",
  "embers",
  "confetti",
  "meteor",
  "seeds",
  "rain",
  "fireworks",
  "smoke",
  "dust",
  "aurora",
  "frost",
  "blossom",
  "stardust",
  "cometShower",
  "galaxy",
  "nebula",
  "supernova",
  "lightning",
  "hail",
  "mist",
  "windyLeaves",
  "thunderstorm",
  "fairyDust",
  "enchanted",
  "potionBubbles",
  "wisps",
  "runes",
  "pollen",
  "mapleLeaves",
  "sakura",
  "dandelion",
  "mossSpores",
  "partyConfetti",
  "glowSticks",
  "disco",
  "balloons",
  "streamers",
] as const;

export type CursorTrailKey = (typeof CURSOR_TRAIL_KEYS)[number];

export interface StorefrontEffects {
  ambient: {
    effect: AmbientEffectKey;
    color: string;
    /** 1 (barely there) to 5 (heavy). Caps the particle count. */
    intensity: number;
  };
  cursor: {
    trail: CursorTrailKey;
    color: string;
    /** Hides the native pointer so the trail *is* the cursor. */
    hideNativeCursor: boolean;
  };
}

export interface StorefrontAppearance {
  theme: StorefrontTheme;
  effects: StorefrontEffects;
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
  storage?: "r2" | "git";
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
