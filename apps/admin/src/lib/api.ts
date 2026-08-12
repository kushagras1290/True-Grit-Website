/**
 * Admin API client.
 *
 * With `VITE_API_URL` set, requests hit the FastAPI admin endpoints with
 * credentials. Without it (demo-data mode) the client resolves the
 * deterministic fixture catalogue so the console is fully reviewable before
 * Cloudflare resources exist.
 */

import type {
  AdminArticleDetail,
  AdminArticleRow,
  AdminBundleDetail,
  AdminBundleItem,
  AdminBundleRow,
  AdminCategoryRow,
  AdminContentCommentRow,
  AdminDbBrowserTableData,
  AdminDiscussionDetail,
  AdminDiscussionRow,
  AdminFarmRequestDetail,
  AdminFarmRequestRow,
  AdminInventoryProductGroup,
  AdminInventoryRow,
  AdminMediaAssetRow,
  AdminOrderRow,
  AdminProductRow,
  AdminPromotionDetail,
  AdminPromotionRow,
  AdminRecipeDetail,
  AdminRecipeRow,
  AdminReturnRequestDetail,
  AdminReturnRequestRow,
  AdminReviewRow,
  AdminRouteSeo,
  AdminServerLogRow,
  AdminSubmissionDetail,
  AdminSubmissionRow,
  AdminUserRow,
  AmbientEffectKey,
  AnalyticsOverview,
  AuditLogRow,
  CommunitySettings,
  ContentBlock,
  CursorTrailKey,
  PublicPageBlock,
  ReportDefinitionSummary,
  ReportRunResult,
  StorefrontEffects,
  StorefrontSettings,
  StorefrontSettingsResponse,
  StorefrontTheme,
  SubscriptionRow,
  ThemeTokenKey,
  ThemeTokens,
} from "@truegrit/contracts";
import { AMBIENT_EFFECT_KEYS, CURSOR_TRAIL_KEYS, THEME_TOKEN_KEYS } from "@truegrit/contracts";
import {
  adminBundleDetails,
  adminBundles,
  analyticsOverview,
  adminCategories,
  adminInventory,
  adminOrders,
  adminProducts,
  adminPromotions,
  adminReviews,
  adminSubscriptions,
  adminUsers,
  articles as demoArticles,
  auditLog,
  featuredPromotionFixture,
  homePage,
  products,
  recipes as demoRecipes,
} from "@truegrit/contracts/fixtures";
import { resizeImageToSpec } from "./image-resize";
import type { ImageSpecification } from "./image-specifications";

const API_URL: string | undefined = import.meta.env.VITE_API_URL as string | undefined;
export const adminApiBaseUrl = (API_URL ?? "").replace(/\/+$/, "");
const DEMO_AUTH_KEY = "truegrit.admin.session";
const DEMO_EMAIL = "admin@truegrit.test";
const DEMO_PASSWORD = "admin123";
export const ADMIN_AUTH_EXPIRED_EVENT = "truegrit.admin.auth-expired";

export const demoMode = !API_URL;

/**
 * Which sender actually handled a transactional email.
 *
 * `"console"` means the API has no mail transport configured and only logged
 * the message — the send "succeeded" and nothing was delivered. Anything
 * reporting a send to a human has to distinguish that case, or it will tell an
 * operator an invitation arrived when it never left the process.
 */
export type EmailTransport = "resend" | "smtp" | "console";

/** Mirrors migration 0002/0081's seeded 'diet' tag_group rows so the
 *  product editor's checkbox list is reviewable without an API. */
const DEMO_DIET_TAGS: AdminDietTagOption[] = [
  { id: "tag_dairy_free", label: "Dairy Free" },
  { id: "tag_gluten_free", label: "Gluten Free" },
  { id: "tag_nut_free", label: "Nut Free" },
  { id: "tag_plant_based", label: "Plant Based" },
  { id: "tag_vegan", label: "Vegan" },
  { id: "tag_vegetarian", label: "Vegetarian" },
];

/** Mirrors database/seeds/development.sql's seeded certifications. */
const DEMO_CERTIFICATIONS: AdminCertificationOption[] = [
  { id: "cert_india_organic", name: "India Organic (NPOP)" },
  { id: "cert_jaivik_bharat", name: "Jaivik Bharat" },
  { id: "cert_pgs_india", name: "PGS-India Green" },
];

/** A couple of representative rows so the Gift Cards page is reviewable
 *  without an API -- gift cards are issued at runtime, not seeded, so there
 *  is no shared fixtures-package entry to reuse here. */
const DEMO_GIFT_CARDS: AdminGiftCardRow[] = [
  {
    id: "gft_demo_diwali",
    code: "DIWALI500",
    initialBalanceMinor: 50_000,
    balanceMinor: 32_500,
    currencyCode: "INR",
    status: "active",
    issuedToEmail: "priya@example.test",
    note: "Diwali gift for a repeat customer",
    expiresAt: null,
    createdAt: "2026-07-01T00:00:00Z",
  },
  {
    id: "gft_demo_spent",
    code: "WELCOME200",
    initialBalanceMinor: 20_000,
    balanceMinor: 0,
    currencyCode: "INR",
    status: "active",
    issuedToEmail: null,
    note: null,
    expiresAt: null,
    createdAt: "2026-06-15T00:00:00Z",
  },
];

/** Mirrors the shipped defaults in migration 0040 so the switches page is
 *  reviewable without an API. */
const DEMO_STOREFRONT_SETTINGS: StorefrontSettingsResponse = {
  settings: {
    googleSignIn: true,
    facebookSignIn: true,
    phoneOtpSignIn: true,
    passwordSignIn: true,
    registration: true,
    payments: true,
    paymentsDisabledNotice:
      "We are not taking orders at the moment. Leave your details and we will get in touch as soon as ordering reopens.",
    // Off by default (migration 0060) -- an operator switches this on once a
    // promotion is actually configured, matching the real shipped default.
    promotions: false,
    // On by default (matches the API's shipped default) -- recommendations
    // need no setup, they are computed live from real order data.
    recommendations: true,
    // Off by default (migration 0064) -- not needed at launch, matching the
    // real shipped default.
    subscriptions: false,
    // On by default, same reasoning as recommendations -- no setup needed.
    dietCertFilters: true,
    // Off by default (migration 0082) -- real stored value, same reasoning
    // as promotions.
    giftCards: false,
    loyalty: false,
    pickup: false,
    preorders: false,
    deliveryZones: false,
    b2b: false,
    blogBannerImageUrl: "",
    blogBannerImageAlt: "",
    farmsBannerImageUrl: "",
    farmsBannerImageAlt: "",
  },
  effective: {
    googleSignIn: true,
    facebookSignIn: true,
    phoneOtpSignIn: true,
    passwordSignIn: true,
    registration: true,
    payments: true,
    promotions: false,
    recommendations: true,
    subscriptions: false,
    dietCertFilters: true,
    giftCards: false,
    loyalty: false,
    pickup: false,
    preorders: false,
    deliveryZones: false,
    b2b: false,
    anySignInAvailable: true,
  },
};

async function demo<T>(data: T): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, 120));
  return structuredClone(data);
}

function notifyAuthExpired(path: string) {
  if (typeof window === "undefined") return;
  if (path === "/v1/admin/me" || path === "/v1/admin/auth/login") return;
  window.dispatchEvent(new CustomEvent(ADMIN_AUTH_EXPIRED_EVENT));
}

async function apiErrorFromResponse(response: Response, path: string): Promise<ApiError> {
  const body = (await response.json().catch(() => null)) as {
    error?: { code?: string; message?: string; details?: Record<string, unknown> };
  } | null;
  if (response.status === 401) notifyAuthExpired(path);
  return new ApiError(
    body?.error?.message ?? `Request failed (${response.status})`,
    response.status,
    body?.error?.code ?? "request_failed",
    body?.error?.details,
  );
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { credentials: "include" });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  return (await response.json()) as T;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  return (await response.json()) as T;
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "PATCH",
    credentials: "include",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  return (await response.json()) as T;
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "PUT",
    credentials: "include",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  return (await response.json()) as T;
}

async function postFile<T>(path: string, file: File): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": file.type || "application/octet-stream" },
    body: file,
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  return (await response.json()) as T;
}

async function del<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  return (await response.json()) as T;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
    public details?: Record<string, unknown>,
  ) {
    super(message);
  }
}

/**
 * Friendly wait-time message for a rate-limited response, e.g. "Too many
 * attempts. Try again in about 5 minutes." Returns the backend's own message
 * when the error isn't a rate limit, or when it didn't include a reset time.
 */
export function describeRateLimitError(error: ApiError): string {
  if (error.status !== 429) return error.message;
  const retryAfterSeconds = error.details?.retryAfterSeconds;
  if (typeof retryAfterSeconds !== "number" || !Number.isFinite(retryAfterSeconds)) {
    return error.message;
  }
  const minutes = Math.max(1, Math.round(retryAfterSeconds / 60));
  return `Too many attempts. Try again in about ${minutes} minute${minutes === 1 ? "" : "s"}.`;
}

export interface AdminLinkedProduct {
  id: string;
  name: string;
  slug: string;
  status: string;
}

export interface AdminProductImage {
  id: string;
  imageUrl: string;
  imageAlt: string | null;
}

export interface AdminDietTagOption {
  id: string;
  label: string;
}

export interface AdminCertificationOption {
  id: string;
  name: string;
}

export interface AdminGiftCardRow {
  id: string;
  code: string;
  initialBalanceMinor: number;
  balanceMinor: number;
  currencyCode: string;
  status: "active" | "cancelled" | "expired";
  issuedToEmail: string | null;
  note: string | null;
  expiresAt: string | null;
  createdAt: string;
}

export interface AdminGiftCardDetail extends AdminGiftCardRow {
  redemptions: Array<{
    orderId: string;
    orderReference: string;
    amountMinor: number;
    redeemedAt: string;
  }>;
}

export interface AdminProductDetail {
  id: string;
  name: string;
  slug: string;
  shortDescription: string;
  /** Traceability copy (migration 0080), shown on the public product page
   *  when set -- free text, not a structured date. */
  harvestNote: string;
  growingMethod: string;
  storageGuidance: string;
  productType: string;
  status: string;
  farmName: string;
  farmId: string | null;
  categoryIds: string[];
  /** tag_group = 'diet' tag ids (migration 0081) and approved certification
   *  ids (migration 0002/0081) currently assigned to this product. */
  dietTagIds: string[];
  certificationIds: string[];
  seoTitle: string;
  seoDescription: string;
  indexingPolicy: "index" | "noindex";
  imageUrl: string;
  imageAlt: string;
  /** Gallery photos beyond the main image above -- shown only on the
   *  storefront product page's image viewer (migration 0066). */
  images: AdminProductImage[];
  updatedAt: string;
  releaseScope: "global" | "selected";
  releaseCountries: string[];
  returnEligible: boolean;
  /** Per-product order/payment switch (migration 0048), independent of the
   *  site-wide one on Site Control. False keeps the product page live and
   *  browsable while pulling only "Add to basket". */
  acceptsOrders: boolean;
  /** Overrides the site-wide payments switch for this product in either
   *  direction (migration 0069): "inherit" follows it, "force_enabled" takes
   *  orders even while payments are off site-wide, "force_disabled" blocks
   *  orders even while payments are on. */
  paymentsOverride: "inherit" | "force_enabled" | "force_disabled";
  linkedProducts: AdminLinkedProduct[];
  variants: Array<{
    id: string;
    name: string;
    sku: string;
    status: string;
    listMinor: number | null;
    saleMinor: number | null;
    available: number;
    isDefault: boolean;
  }>;
}

export interface AdminCategoryDetail {
  id: string;
  name: string;
  slug: string;
  shortDescription: string;
  heroEyebrow: string;
  heroTitle: string;
  heroDescription: string;
  seasonLabel: string;
  themeKey: string;
  visibility: string;
  status: string;
  seoTitle: string;
  seoDescription: string;
  indexingPolicy: "index" | "noindex";
  heroImageUrl: string;
  heroImageAlt: string;
  thumbnailImageUrl: string;
  thumbnailImageAlt: string;
  productAssignmentMode: string;
  releaseScope: "global" | "selected";
  releaseCountries: string[];
  updatedAt: string;
}

export interface AdminRole {
  id: string;
  key: string;
  name: string;
  description: string;
  isSystem: boolean;
  locked: boolean;
  permissionIds: string[];
  permissionKeys: string[];
}

export interface AdminPermission {
  id: string;
  key: string;
  description: string;
}

export interface AdminFarmRow {
  id: string;
  name: string;
  slug: string;
  farmerName: string;
  region: string;
  countryCode: string;
  establishedYear: number | null;
  summary: string;
  status: string;
  productCount: number;
  updatedAt: string;
  heroImageUrl: string | null;
  heroImageAlt: string | null;
  indexingPolicy: "index" | "noindex";
}

export interface AdminContactMessageRow {
  id: string;
  name: string;
  email: string;
  /** E.164, or null for a message sent before migration 0045 added the
   *  column. Most contact traffic is settled by phone, so this is the field
   *  staff actually reach for. */
  phone: string | null;
  subject: string;
  message: string;
  status: "new" | "read" | "archived";
  createdAt: string;
  handledAt: string | null;
}

export type ArchiveKind = "product" | "category" | "farm" | "page" | "article" | "recipe";

export interface ArchiveRow {
  id: string;
  kind: ArchiveKind;
  name: string;
  slug: string;
  status: string;
  archivedAt: string;
  updatedAt: string;
  updatedBy: string;
  detail: string;
}

export interface AdminOrderDetail {
  id: string;
  publicReference: string;
  customerEmail: string;
  currencyCode: string;
  subtotalMinor: number;
  discountMinor: number;
  deliveryMinor: number;
  taxMinor: number;
  totalMinor: number;
  giftCardAppliedMinor: number;
  giftCardCode: string | null;
  orderStatus: string;
  paymentStatus: string;
  fulfilmentStatus: string;
  deliveryStatus: string;
  placedAt: string;
  items: Array<{
    id: string;
    productName: string;
    variantName: string;
    sku: string;
    quantity: number;
    unitMinor: number;
    lineTotalMinor: number;
  }>;
  payment: {
    provider: string;
    status: string;
    amountMinor: number;
    currencyCode: string;
    refundedMinor: number;
  } | null;
}

export interface AdminRefundRow {
  id: string;
  orderId: string;
  orderReference: string;
  currencyCode: string;
  actorName: string;
  paymentStatus: string | null;
  refundedMinor: number | null;
  reason: string | null;
  providerRefundId: string | null;
  createdAt: string;
}

export interface AdminSearchProductResult {
  id: string;
  name: string;
  slug: string;
  sku: string;
}

export interface AdminSearchOrderResult {
  id: string;
  publicReference: string;
  customerEmail: string | null;
  orderStatus: string;
  totalMinor: number;
  currencyCode: string;
}

export interface AdminSearchUserResult {
  id: string;
  displayName: string;
  email: string;
  status: string;
}

export interface AdminSearchCategoryResult {
  id: string;
  name: string;
  slug: string;
  status: string;
}

export interface AdminSearchResults {
  products: AdminSearchProductResult[];
  orders: AdminSearchOrderResult[];
  users: AdminSearchUserResult[];
  categories: AdminSearchCategoryResult[];
}

export interface Me {
  id: string;
  displayName: string;
  email: string;
  permissions: string[];
  farmId?: string | null;
  farmName?: string | null;
  isSuperAdmin: boolean;
}

export interface AdminNotification {
  id: string;
  title: string;
  message: string;
  count: number;
  href: string;
  severity: "warning" | "danger" | "info";
}

export interface ConversationParticipant {
  userId: string;
  displayName: string;
  roles: string[];
}

export interface ConversationSummary {
  id: string;
  type: "group" | "direct";
  name: string | null;
  createdAt: string;
  lastMessageBody: string | null;
  lastMessageAt: string | null;
  unreadCount: number;
  participants: ConversationParticipant[];
}

export interface ChatMessage {
  id: string;
  senderId: string;
  senderName: string;
  body: string;
  createdAt: string;
}

export interface ConversationHistory {
  conversationId: string;
  messages: ChatMessage[];
  limit: number;
}

export interface SupportBotChatTurn {
  role: "user" | "assistant";
  content: string;
}

export type SupportBotScope = "admin" | "storefront";

export interface SupportBotKnowledgeEntry {
  id: string;
  scope: SupportBotScope;
  title: string;
  keywords: string;
  content: string;
  isBuiltin: boolean;
  updatedAt: string;
}

export type SupportBotTuningKey =
  "historyTurns" | "knowledgeSnippets" | "searchResults" | "policyChars";

export interface SupportBotSettings {
  admin: boolean;
  storefront: boolean;
  /** How many prior turns the client may replay into the prompt. */
  historyTurns: number;
  /** How many knowledge-base entries are embedded as reference material. */
  knowledgeSnippets: number;
  /** How many hits the storefront bot's search tools return per call. */
  searchResults: number;
  /** How much of a policy page's text the bot may quote. */
  policyChars: number;
  /** Hex colour for both chat widgets; blank means inherit the site brand. */
  widgetColor: string;
  /** Space-separated page slugs the storefront bot may quote verbatim. */
  policyPages: string;
}

export interface SiteControl {
  heroEyebrow: string;
  heroHeading: string;
  heroText: string;
  heroImageUrl: string;
  heroImageAlt: string;
  heroSlides: Array<{
    imageUrl: string;
    imageAlt: string;
    href: string;
    label: string;
    enabled: boolean;
  }>;
  primaryActionLabel: string;
  primaryActionHref: string;
  secondaryActionLabel: string;
  secondaryActionHref: string;
  seoTitle: string;
  seoDescription: string;
  seoKeywords: string;
  featuredCategories: string[];
  freshFavourites: string[];
  /** How many banner slides Homepage Settings will curate. Stored in
   *  `app_settings`, so raising it is an admin change rather than a deploy. */
  heroMaxSlides: number;
  /** The structural ceiling the block model enforces regardless of the setting
   *  above — shown so an operator raising the cap knows how far it can go. */
  heroSlidesHardLimit: number;
}

export interface SiteDocuments {
  robotsTxt: string;
  sitemapXml: string;
  llmsTxt: string;
}

/** One announcement scope: `'global'` (the site-wide banner) or a two-letter
 *  country code. A country row fully replaces the global banner for its
 *  visitors when active — there is nothing to merge, unlike theme colours. */
export interface AnnouncementScopeRow {
  scope: string;
  active: boolean;
  message: string;
  path: string;
  updatedAt: string;
}

export interface AnnouncementsResponse {
  scopes: AnnouncementScopeRow[];
}

/**
 * One block of the homepage, as Homepage Settings sees it.
 *
 * `label` and `summary` are rendered server-side so the console never has to
 * guess at a block type it was not built with. `removable` is false for the
 * three sections Site Control's own editors bind to — they can be switched off
 * but not deleted.
 */
export interface HomepageSection {
  id: string;
  type: string;
  label: string;
  heading: string;
  summary: string;
  enabled: boolean;
  removable: boolean;
  props: Record<string, unknown>;
}

export interface HomepageSectionsResponse {
  sections: HomepageSection[];
  addableTypes: Array<{ type: string; label: string }>;
}

/** Per-country visibility overrides: `{ IN: { blk_123: true, blk_456: false } }`.
 *  A country absent from this map has no overrides at all — every section
 *  there falls back to its own tickbox in the section list above. A section
 *  id absent from a present country's map falls back the same way; only ids
 *  actually listed are forced on or off for that country. */
export interface HomepageCountryOverridesResponse {
  overrides: Record<string, Record<string, boolean>>;
}

/** A signed markup (positive) or genuine discount (negative), targeting one
 *  product, one whole category, or every product — combined with `'global'`
 *  or a country scope. `productId` and `categoryId` are mutually exclusive;
 *  both null means "every product" for that scope. Resolution is
 *  most-specific-wins, not a merge — see `services/price_adjustments.py`. */
export interface PriceAdjustmentRule {
  id: string;
  scope: string;
  productId: string | null;
  productName: string | null;
  productSlug: string | null;
  categoryId: string | null;
  categoryName: string | null;
  categorySlug: string | null;
  percent: number;
  active: boolean;
  updatedAt: string;
}

export interface PriceAdjustmentsResponse {
  rules: PriceAdjustmentRule[];
}

export interface CurrencyRate {
  currencyCode: string;
  locale: string;
  /** Decimal string: units of this currency displayed for one INR. */
  ratePerInr: string;
  active: boolean;
  updatedAt: string;
}

export interface CurrencyRatesResponse {
  baseCurrency: "INR";
  rates: CurrencyRate[];
}

/** One themed scope: the site-wide palette (`global`), a single page (`/shop`),
 *  or a country (`country:IN`). `hasEffectsOverride` is only ever true for a
 *  country scope — a page cannot carry its own ambient effect or cursor
 *  trail, only its own colours. */
export interface ThemeScopeRow {
  scope: string;
  tokens: ThemeTokens;
  hasEffectsOverride: boolean;
  updatedAt: string;
}

/**
 * The admin console's *raw* view of the theme: every scope kept separate,
 * never blended for a particular visitor. This is why it is its own type
 * rather than the storefront-facing `StorefrontTheme` — the public API
 * resolves `global` per visitor's country before it ever reaches the
 * storefront, but the console has to see the country layer on its own to let
 * an owner edit it.
 */
export interface AdminStorefrontTheme {
  global: ThemeTokens;
  countries: Record<string, ThemeTokens>;
  pages: Record<string, ThemeTokens>;
}

/**
 * Everything the Appearance page needs in one payload.
 *
 * `effects` is the site-wide default, in exactly the shape the storefront
 * receives when no country override applies — so the console's default-effect
 * preview renders against the same values the live site does. `countryEffects`
 * is sparse: only countries an owner has actually given their own ambient
 * effect and/or cursor trail appear in it. The `*Keys` lists come from the API
 * too, so a token or effect added on the server appears in the console without
 * a matching front-end release.
 */
export interface AppearanceResponse {
  theme: AdminStorefrontTheme;
  effects: StorefrontEffects;
  countryEffects: Record<string, StorefrontEffects>;
  scopes: ThemeScopeRow[];
  tokenKeys: ThemeTokenKey[];
  ambientEffects: AmbientEffectKey[];
  cursorTrails: CursorTrailKey[];
}

export interface CmsPageRow {
  id: string;
  slug: string;
  title: string;
  pageType: string;
  templateKey: string;
  status: string;
  seoTitle: string;
  seoDescription: string;
  seoKeywords: string;
  indexingPolicy: "index" | "noindex";
  updatedAt: string;
  blockCount: number;
}

export interface CmsPageDetail extends CmsPageRow {
  blocks: PublicPageBlock[];
}

export interface PageTranslationSummary {
  locale: string;
  autoTranslated: boolean;
  updatedAt: string;
}

export interface PageTranslation {
  locale: string;
  content: { blocks: PublicPageBlock[] };
  autoTranslated: boolean;
  updatedAt: string | null;
}

/** Per-locale field overrides for database-sourced content (migration 0068)
 *  -- navigation labels, category/product names and descriptions, article/
 *  recipe titles and excerpts. One shape for every entity type; which keys
 *  `fields` actually carries is entity-type-specific (mirrors
 *  `services.entity_translation.TRANSLATABLE_FIELDS` on the API). */
export type EntityTranslationType =
  "navigation_item" | "category" | "product" | "article" | "recipe";

export interface EntityTranslationSummary {
  locale: string;
  autoTranslated: boolean;
  updatedAt: string;
}

export interface EntityTranslation {
  locale: string;
  fields: Record<string, string>;
  autoTranslated: boolean;
  updatedAt: string | null;
}

/** One farm's revenue line on the Revenue page.
 *
 * Every amount is integer minor units (ADR-006) — paise for INR. `commissionBps`
 * is basis points (1500 = 15%); `commissionSource` says whether that came from
 * this farm's own override or the house default.
 *
 * `outstandingPayoutMinor` is the number the "Issue payment" button pays: net
 * revenue on lines no payout has settled yet, less the platform's cut. */
export interface FarmRevenueRow {
  farmId: string;
  farmName: string;
  farmSlug: string;
  farmerName: string;
  region: string;
  status: string;
  currencyCode: string;
  ownerUserId: string | null;
  ownerName: string;
  ownerEmail: string;
  commissionBps: number;
  commissionPercent: number;
  commissionSource: "farm" | "default";
  orderCount: number;
  grossMinor: number;
  refundedMinor: number;
  netRevenueMinor: number;
  commissionMinor: number;
  farmEarningsMinor: number;
  paidOutMinor: number;
  payoutCount: number;
  outstandingItemCount: number;
  outstandingGrossMinor: number;
  outstandingRefundedMinor: number;
  outstandingNetMinor: number;
  outstandingCommissionMinor: number;
  outstandingPayoutMinor: number;
}

export interface FarmRevenueSummary {
  defaultCommissionBps: number;
  defaultCommissionPercent: number;
  farms: FarmRevenueRow[];
  totals: {
    grossMinor: number;
    refundedMinor: number;
    netRevenueMinor: number;
    commissionMinor: number;
    farmEarningsMinor: number;
    paidOutMinor: number;
    outstandingPayoutMinor: number;
  };
}

export interface FarmRevenueLine {
  orderItemId: string;
  orderId: string;
  orderReference: string;
  orderedAt: string;
  productName: string;
  variantName: string;
  quantity: number;
  currencyCode: string;
  grossMinor: number;
  refundedMinor: number;
  netMinor: number;
  /** True once a payout has settled this line; it can never be paid again. */
  settled: boolean;
  payoutId: string | null;
}

export interface FarmPayout {
  id: string;
  farmId: string;
  farmName: string;
  currencyCode: string;
  grossMinor: number;
  refundedMinor: number;
  netRevenueMinor: number;
  commissionBps: number;
  commissionPercent: number;
  commissionMinor: number;
  payoutMinor: number;
  itemCount: number;
  status: string;
  reference: string;
  note: string;
  provider: string;
  providerReference: string;
  paidToUserId: string | null;
  paidToName: string;
  createdAt: string;
  createdByName: string;
}

export interface FarmRevenueDetail {
  summary: FarmRevenueRow;
  lines: FarmRevenueLine[];
  payouts: FarmPayout[];
}

export interface FarmPayoutResult {
  payoutId: string;
  farmId: string;
  farmName: string;
  currencyCode: string;
  payoutMinor: number;
  commissionMinor: number;
  itemCount: number;
}

const DEMO_REVENUE: FarmRevenueSummary = {
  defaultCommissionBps: 1500,
  defaultCommissionPercent: 15,
  farms: [],
  totals: {
    grossMinor: 0,
    refundedMinor: 0,
    netRevenueMinor: 0,
    commissionMinor: 0,
    farmEarningsMinor: 0,
    paidOutMinor: 0,
    outstandingPayoutMinor: 0,
  },
};

/** Mirrors the API's own grouping (`repositories/admin.py` `list_inventory`):
 *  one entry per product, alphabetical, each carrying its variants together
 *  rather than repeating the product name on a separate row per variant. */
function groupInventoryByProduct(rows: AdminInventoryRow[]): AdminInventoryProductGroup[] {
  const order: string[] = [];
  const byProduct = new Map<string, AdminInventoryProductGroup>();
  for (const row of rows) {
    let group = byProduct.get(row.productId);
    if (!group) {
      group = {
        productId: row.productId,
        productName: row.productName,
        productStatus: row.productStatus,
        variants: [],
      };
      byProduct.set(row.productId, group);
      order.push(row.productId);
    }
    group.variants.push(row);
  }
  return order
    .map((productId) => byProduct.get(productId)!)
    .sort((a, b) => a.productName.localeCompare(b.productName));
}

function demoFarmRevenueDetail(farmId: string): FarmRevenueDetail {
  return {
    summary: {
      farmId,
      farmName: "Demo farm",
      farmSlug: farmId,
      farmerName: "",
      region: "",
      status: "published",
      currencyCode: "INR",
      ownerUserId: null,
      ownerName: "",
      ownerEmail: "",
      commissionBps: 1500,
      commissionPercent: 15,
      commissionSource: "default",
      orderCount: 0,
      grossMinor: 0,
      refundedMinor: 0,
      netRevenueMinor: 0,
      commissionMinor: 0,
      farmEarningsMinor: 0,
      paidOutMinor: 0,
      payoutCount: 0,
      outstandingItemCount: 0,
      outstandingGrossMinor: 0,
      outstandingRefundedMinor: 0,
      outstandingNetMinor: 0,
      outstandingCommissionMinor: 0,
      outstandingPayoutMinor: 0,
    },
    lines: [],
    payouts: [],
  };
}

const DEMO_ME: Me = {
  id: "usr_admin",
  displayName: "Asha Rao",
  email: "admin@truegrit.test",
  isSuperAdmin: true,
  permissions: [
    "products.view",
    "products.create",
    "products.edit",
    "products.approve",
    "products.publish",
    "categories.view",
    "categories.create",
    "categories.edit",
    "categories.approve",
    "categories.publish",
    "pages.view",
    "pages.edit",
    "pages.publish",
    "media.view",
    "media.upload",
    "orders.view",
    "orders.cancel",
    "orders.refund",
    "inventory.view",
    "inventory.adjust",
    "users.view",
    "users.invite",
    "users.manage_roles",
    "audit.view",
    "settings.view",
    "settings.edit",
    "revenue.view",
    "revenue.manage",
  ],
};

// ---------------------------------------------------------------------------
// Demo-mode homepage sections
//
// Mirrors `api/admin.py` closely enough that Homepage Settings is genuinely
// reviewable without an API: toggling, reordering, adding and deleting all
// behave, against an in-memory copy of the fixture homepage that resets on
// reload. The real labels and summaries come from the server.
// ---------------------------------------------------------------------------

const DEMO_SECTION_LABELS: Record<string, string> = {
  hero: "Banner carousel",
  category_collection: "Category row",
  product_collection: "Product row",
  page_links: "Page snippets",
  farmer_story: "Farmer quote",
  faq: "Questions and answers",
  rich_text: "Text block",
  newsletter: "Newsletter signup",
  reviews_showcase: "Customer reviews",
  promotion_banner: "Promotions banner",
  recommendations: "Recommended products",
  image_banner: "Motto banner",
};

const DEMO_ADDABLE_TYPES = [
  "page_links",
  "rich_text",
  "faq",
  "farmer_story",
  "newsletter",
  "reviews_showcase",
  "promotion_banner",
  "recommendations",
  "image_banner",
];

const DEMO_NEW_SECTION_PROPS: Record<string, Record<string, unknown>> = {
  page_links: {
    heading: "More from True Grit",
    intro: "",
    items: [
      {
        label: "Shop the market",
        description: "Every organic product we carry, in one place.",
        href: "/shop",
        enabled: true,
      },
    ],
  },
  rich_text: { paragraphs: ["Replace this with the copy for the new section."] },
  faq: {
    heading: "Common questions",
    items: [{ question: "Replace this question.", answer: "Replace this answer." }],
  },
  farmer_story: {
    farmSlug: "",
    quote: "Replace this with the grower's words.",
    attribution: "Grower name, farm name",
  },
  newsletter: {
    heading: "A slower, better way to eat.",
    consentText: "One considered letter a month. No noise, unsubscribe anytime.",
  },
  reviews_showcase: {
    heading: "What customers are saying",
    subheading: "",
    source: "rule",
    reviewIds: [],
    limit: 8,
    minRating: 4,
  },
  promotion_banner: {
    source: "rule",
    promotionId: null,
  },
  recommendations: {
    heading: "Customer favourites",
    subheading: "Picked by shoppers",
    limit: 8,
  },
  image_banner: {
    imageUrl: "/homepage-hero.png",
    imageAlt: "True Grit -- Pure By Nature, True By Choice",
    href: null,
  },
};

const DEMO_CLAIMED_SECTION_TYPES = ["hero", "category_collection", "product_collection"];

let demoHomepageBlocks: PublicPageBlock[] | null = null;

function demoBlocks(): PublicPageBlock[] {
  demoHomepageBlocks ??= structuredClone(homePage.blocks);
  return demoHomepageBlocks;
}

function demoSectionSummary(block: PublicPageBlock): string {
  const plural = (count: number, one: string, many: string) =>
    `${count} ${count === 1 ? one : many}`;
  switch (block.type) {
    case "hero":
      return plural(block.props.slides?.length ?? 0, "banner slide", "banner slides");
    case "category_collection":
      return plural(block.props.categorySlugs.length, "category", "categories");
    case "product_collection":
      return plural(block.props.productSlugs.length, "product", "products");
    case "page_links":
      return plural(block.props.items.length, "page snippet", "page snippets");
    case "faq":
      return plural(block.props.items.length, "question", "questions");
    case "rich_text":
      return plural(block.props.paragraphs.length, "paragraph", "paragraphs");
    case "farmer_story":
      return block.props.attribution || "No attribution";
    case "newsletter":
      return block.props.heading || "Newsletter signup";
    case "reviews_showcase":
      return block.props.source === "manual"
        ? plural(block.props.reviewIds.length, "featured review", "featured reviews")
        : `Top-rated reviews, ${block.props.minRating}+ stars`;
    case "promotion_banner":
      return block.props.source === "manual" ? "One specific promotion" : "Best active promotion";
    case "recommendations":
      return `Top ${block.props.limit} best sellers, computed live from orders`;
    case "image_banner":
      return block.props.imageAlt || "No image set";
  }
}

function demoSections(): HomepageSectionsResponse {
  const blocks = demoBlocks();
  const claimed = new Set(
    DEMO_CLAIMED_SECTION_TYPES.map(
      (type) => blocks.find((block) => block.type === type)?.id,
    ).filter((id): id is string => Boolean(id)),
  );
  return {
    sections: blocks.map((block) => ({
      id: block.id,
      type: block.type,
      label: DEMO_SECTION_LABELS[block.type] ?? block.type,
      heading: "heading" in block.props ? String(block.props.heading ?? "") : "",
      summary: demoSectionSummary(block),
      enabled: block.enabled,
      removable: !claimed.has(block.id),
      props: block.props as unknown as Record<string, unknown>,
    })),
    addableTypes: DEMO_ADDABLE_TYPES.map((type) => ({
      type,
      label: DEMO_SECTION_LABELS[type] ?? type,
    })),
  };
}

function demoSectionIndex(sectionId: string): number {
  const index = demoBlocks().findIndex((block) => block.id === sectionId);
  if (index === -1) {
    throw new ApiError("Homepage section not found.", 404, "not_found");
  }
  return index;
}

// Demo-mode appearance. Held in memory so the Appearance page's colour pickers,
// per-page scopes and effect preview all behave without an API; resets on
// reload, like the homepage sections above.
let demoAppearance_: DemoAppearanceState | null = null;

interface DemoAppearanceState {
  theme: AdminStorefrontTheme;
  effects: StorefrontEffects;
  countryEffects: Record<string, StorefrontEffects>;
}

function demoAppearanceState(): DemoAppearanceState {
  demoAppearance_ ??= {
    theme: { global: {}, countries: {}, pages: {} },
    effects: {
      ambient: { effect: "none", color: "#ffffff", intensity: 3 },
      cursor: { trail: "none", color: "#24483a", hideNativeCursor: false },
    },
    countryEffects: {},
  };
  return demoAppearance_;
}

/** Which bucket of `theme` a scope's tokens live in — mirrors the server's
 *  own `is_country_scope()` split between a page path and a `country:XX` code. */
function demoThemeBucket(scope: string): Record<string, ThemeTokens> {
  return scope.startsWith("country:")
    ? demoAppearanceState().theme.countries
    : demoAppearanceState().theme.pages;
}

function demoAppearance(): AppearanceResponse {
  const state = demoAppearanceState();
  return {
    theme: structuredClone(state.theme),
    effects: structuredClone(state.effects),
    countryEffects: structuredClone(state.countryEffects),
    scopes: [
      {
        scope: "global",
        tokens: state.theme.global,
        hasEffectsOverride: false,
        updatedAt: new Date().toISOString(),
      },
      ...Object.entries(state.theme.countries).map(([scope, tokens]) => ({
        scope,
        tokens,
        hasEffectsOverride: scope in state.countryEffects,
        updatedAt: new Date().toISOString(),
      })),
      ...Object.entries(state.theme.pages).map(([scope, tokens]) => ({
        scope,
        tokens,
        hasEffectsOverride: false,
        updatedAt: new Date().toISOString(),
      })),
    ],
    tokenKeys: [...THEME_TOKEN_KEYS],
    ambientEffects: [...AMBIENT_EFFECT_KEYS],
    cursorTrails: [...CURSOR_TRAIL_KEYS],
  };
}

// Demo-mode announcements. Mirrors the shipped seed: one active global row.
let demoAnnouncementRows_: AnnouncementScopeRow[] | null = null;

function demoAnnouncementRows(): AnnouncementScopeRow[] {
  demoAnnouncementRows_ ??= [
    {
      scope: "global",
      active: true,
      message: "Alphonso season is here — orchard-fresh boxes ship every Tuesday.",
      path: "/seasonal",
      updatedAt: new Date().toISOString(),
    },
  ];
  return demoAnnouncementRows_;
}

function demoAnnouncements(): AnnouncementsResponse {
  return { scopes: structuredClone(demoAnnouncementRows()) };
}

// Demo-mode homepage country overrides. Empty by default — every country
// inherits the section list's own tickboxes until one is added here.
let demoHomepageOverrides_: Record<string, Record<string, boolean>> | null = null;

function demoHomepageOverrides(): Record<string, Record<string, boolean>> {
  demoHomepageOverrides_ ??= {};
  return demoHomepageOverrides_;
}

// Demo-mode price adjustments. Empty by default, same as the real seed.
let demoPriceAdjustments_: PriceAdjustmentRule[] | null = null;

function demoPriceAdjustmentRows(): PriceAdjustmentRule[] {
  demoPriceAdjustments_ ??= [];
  return demoPriceAdjustments_;
}

function demoPriceAdjustments(): PriceAdjustmentsResponse {
  return { rules: structuredClone(demoPriceAdjustmentRows()) };
}

function hasDemoSession(): boolean {
  return typeof window !== "undefined" && window.localStorage.getItem(DEMO_AUTH_KEY) === "active";
}

function setDemoSession(active: boolean): void {
  if (typeof window === "undefined") return;
  if (active) {
    window.localStorage.setItem(DEMO_AUTH_KEY, "active");
  } else {
    window.localStorage.removeItem(DEMO_AUTH_KEY);
  }
}

export interface LoyaltyAccountRow {
  id: string;
  customerUserId: string;
  customerEmail: string;
  customerName: string;
  referralCode: string;
  balance: number;
  status: string;
}

export interface PickupPointRow {
  id: string;
  name: string;
  address: Record<string, unknown>;
  hours: string | null;
  phone: string | null;
  status: "active" | "inactive";
}

export interface HarvestWindowRow {
  id: string;
  productId: string;
  productName: string | null;
  title: string | null;
  expectedStart: string;
  expectedEnd: string;
  maxPreorders: number | null;
  currentPreorders: number;
  status: string;
}

export interface PreorderRow {
  id: string;
  orderId: string;
  orderReference: string | null;
  harvestWindowId: string;
  productId: string;
  productName: string | null;
  variantId: string;
  quantity: number;
  status: "reserved" | "ready" | "fulfilled" | "cancelled";
  createdAt: string;
  fulfilledAt: string | null;
}

export interface DeliveryZoneRow {
  id: string;
  name: string;
  postalCodes: string[];
  feeOverrideMinor: number | null;
  freeThresholdOverrideMinor: number | null;
  leadTimeHours: number;
  status: "active" | "inactive";
}

export interface B2BAccountRow {
  id: string;
  companyName: string;
  gstNumber: string | null;
  contactEmail: string | null;
  creditLimitMinor: number;
  paymentTermsDays: number;
  status: "pending" | "active" | "suspended";
}

export interface B2BInvoiceRow {
  id: string;
  orderId: string;
  orderReference: string | null;
  b2bAccountId: string;
  companyName: string | null;
  invoiceNumber: string;
  amountMinor: number;
  currencyCode: string;
  dueDate: string;
  status: "issued" | "paid" | "overdue" | "cancelled";
  paymentReference: string | null;
  issuedAt: string;
  paidAt: string | null;
}

export const api = {
  me: async (): Promise<Me> => {
    if (!demoMode) return get<Me>("/v1/admin/me");
    if (!hasDemoSession()) {
      throw new ApiError("Authentication required.", 401, "authentication_required");
    }
    return demo(DEMO_ME);
  },

  notifications: (): Promise<{ items: AdminNotification[]; total: number }> =>
    demoMode ? demo({ items: [], total: 0 }) : get("/v1/admin/notifications"),

  login: async (email: string, password: string): Promise<void> => {
    if (demoMode) {
      await new Promise((resolve) => setTimeout(resolve, 180));
      if (email.toLowerCase() !== DEMO_EMAIL || password !== DEMO_PASSWORD) {
        throw new ApiError("Invalid admin email or password.", 401, "authentication_required");
      }
      setDemoSession(true);
      return;
    }
    await post<{ ok: boolean }>("/v1/admin/auth/login", { email, password });
  },

  logout: async (): Promise<void> => {
    if (demoMode) {
      setDemoSession(false);
      return;
    }
    await post<{ ok: boolean }>("/v1/admin/auth/logout");
  },

  search: (query: string): Promise<AdminSearchResults> => {
    const empty: AdminSearchResults = { products: [], orders: [], users: [], categories: [] };
    const trimmed = query.trim();
    if (trimmed.length < 2) return demo(empty);
    if (!demoMode)
      return get<AdminSearchResults>(`/v1/admin/search?q=${encodeURIComponent(trimmed)}`);

    const term = trimmed.toLowerCase();
    const matches = (...values: Array<string | null | undefined>) =>
      values.some((value) => value?.toLowerCase().includes(term));

    return demo({
      products: adminProducts
        .filter((product) => matches(product.name, product.sku, product.slug))
        .slice(0, 5)
        .map((product) => ({
          id: product.id,
          name: product.name,
          slug: product.slug,
          sku: product.sku,
        })),
      orders: adminOrders
        .filter((order) => matches(order.publicReference, order.customerEmail))
        .slice(0, 5)
        .map((order) => ({
          id: order.id,
          publicReference: order.publicReference,
          customerEmail: order.customerEmail,
          orderStatus: order.orderStatus,
          totalMinor: order.totalMinor,
          currencyCode: order.currencyCode,
        })),
      users: adminUsers
        .filter((user) => matches(user.displayName, user.email))
        .slice(0, 5)
        .map((user) => ({
          id: user.id,
          displayName: user.displayName,
          email: user.email,
          status: user.status,
        })),
      categories: adminCategories
        .filter((category) => matches(category.name, category.slug))
        .slice(0, 5)
        .map((category) => ({
          id: category.id,
          name: category.name,
          slug: category.slug,
          status: category.status,
        })),
    });
  },

  products: ({
    limit = 25,
    offset = 0,
    search,
  }: { limit?: number; offset?: number; search?: string } = {}): Promise<AdminProductRow[]> =>
    demoMode
      ? demo(adminProducts)
      : get<{ items: AdminProductRow[] }>(
          `/v1/admin/products?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  getProduct: (id: string): Promise<AdminProductDetail> => {
    if (!demoMode) return get<AdminProductDetail>(`/v1/admin/products/${id}`);
    const product = products.find((entry) => entry.id === id);
    if (!product) throw new ApiError("Product not found.", 404, "not_found");
    return demo<AdminProductDetail>({
      id: product.id,
      name: product.name,
      slug: product.slug,
      shortDescription: product.shortDescription,
      harvestNote: "",
      growingMethod: "",
      storageGuidance: "",
      productType: "general",
      status: "published",
      farmName: product.farmName,
      farmId: null,
      categoryIds: [],
      dietTagIds: [],
      certificationIds: [],
      seoTitle: product.seo.title,
      seoDescription: product.seo.description,
      indexingPolicy: product.seo.indexing,
      imageUrl: product.imageUrl ?? "",
      imageAlt: product.imageAlt,
      images: [],
      updatedAt: new Date().toISOString(),
      releaseScope: "global",
      releaseCountries: [],
      returnEligible: true,
      acceptsOrders: true,
      paymentsOverride: "inherit",
      linkedProducts: [],
      variants: product.variants.map((variant, index) => ({
        id: variant.id,
        name: variant.name,
        sku: variant.sku,
        status: "active",
        listMinor: variant.listMinor,
        saleMinor: variant.saleMinor,
        available: 0,
        isDefault: index === 0,
      })),
    });
  },

  createProduct: (input: {
    name: string;
    productType: string;
    slug?: string;
    shortDescription?: string;
  }): Promise<{ id: string; slug: string; status: string }> =>
    demoMode
      ? demo({
          id: `prd_${Date.now().toString(36)}`,
          slug: input.slug ?? "new-product",
          status: "draft",
        })
      : post("/v1/admin/products", input),

  updateProduct: (id: string, input: Record<string, unknown>): Promise<{ id: string }> =>
    demoMode ? demo({ id }) : patch(`/v1/admin/products/${id}`, input),

  createVariant: (
    productId: string,
    input: { name: string; sku: string; listMinor: number; saleMinor?: number | null },
  ): Promise<{ id: string }> =>
    demoMode
      ? demo({ id: `var_${Date.now()}` })
      : post(`/v1/admin/products/${productId}/variants`, input),

  updateVariant: (
    productId: string,
    variantId: string,
    input: { name?: string; sku?: string; listMinor?: number; saleMinor?: number | null },
  ): Promise<{ id: string }> =>
    demoMode
      ? demo({ id: variantId })
      : patch(`/v1/admin/products/${productId}/variants/${variantId}`, input),

  setDefaultVariant: (
    productId: string,
    variantId: string,
  ): Promise<{ id: string; isDefault: boolean }> =>
    demoMode
      ? demo({ id: variantId, isDefault: true })
      : post(`/v1/admin/products/${productId}/variants/${variantId}/set-default`),

  updateProductStatus: (
    productId: string,
    status: "published" | "unpublished",
  ): Promise<{ id: string }> =>
    demoMode
      ? demo({ id: productId })
      : patch(`/v1/admin/products/${productId}/status`, { status }),

  publishProduct: (
    id: string,
    changeSummary?: string,
  ): Promise<{ status: string; version: number }> =>
    demoMode
      ? demo({ status: "published", version: 1 })
      : post(`/v1/admin/products/${id}/publish`, { changeSummary }),

  archiveProduct: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "archived" }) : post(`/v1/admin/products/${id}/archive`),

  deleteProduct: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "archived" }) : del(`/v1/admin/products/${id}`),

  deleteProducts: (productIds: string[]): Promise<{ deletedIds: string[]; count: number }> =>
    demoMode
      ? demo({ deletedIds: productIds, count: productIds.length })
      : post("/v1/admin/products/bulk-delete", { productIds }),

  archive: ({
    limit = 25,
    offset = 0,
    search,
  }: { limit?: number; offset?: number; search?: string } = {}): Promise<ArchiveRow[]> =>
    demoMode
      ? demo([
          {
            id: "demo_arch_product",
            kind: "product",
            name: "Archived sample product",
            slug: "archived-sample-product",
            status: "archived",
            archivedAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            updatedBy: "Demo Admin",
            detail: "Demo farm",
          },
        ])
      : get<{ items: ArchiveRow[] }>(
          `/v1/admin/archive?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  restoreArchiveItem: (
    kind: ArchiveKind,
    id: string,
  ): Promise<{ id: string; kind: ArchiveKind; status: string }> =>
    demoMode
      ? demo({ id, kind, status: "draft" })
      : post(`/v1/admin/archive/${kind}/${id}/restore`),

  purgeArchiveItems: (
    items: Array<{ kind: ArchiveKind; id: string }>,
  ): Promise<{ deleted: Array<{ kind: ArchiveKind; id: string }>; count: number }> =>
    demoMode
      ? demo({ deleted: items, count: items.length })
      : post("/v1/admin/archive/bulk-delete", { items }),

  categories: ({
    limit = 25,
    offset = 0,
    search,
  }: { limit?: number; offset?: number; search?: string } = {}): Promise<AdminCategoryRow[]> =>
    demoMode
      ? demo(adminCategories)
      : get<{ items: AdminCategoryRow[] }>(
          `/v1/admin/categories?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  // Small, fixed vocabularies (a handful of rows each) -- unlike categories()
  // these are never paginated or searched, and demo mode falls back to a
  // literal list matching migration 0002/0081's seeded labels rather than
  // pulling in a whole fixtures-package entry for four rows.
  dietTags: (): Promise<AdminDietTagOption[]> =>
    demoMode
      ? demo(DEMO_DIET_TAGS)
      : get<{ items: AdminDietTagOption[] }>("/v1/admin/diet-tags").then((body) => body.items),

  createDietTag: (label: string): Promise<AdminDietTagOption> =>
    demoMode
      ? demo({ id: `tag_demo_${Date.now()}`, label })
      : post("/v1/admin/diet-tags", { label }),

  updateDietTag: (id: string, label: string): Promise<AdminDietTagOption> =>
    demoMode ? demo({ id, label }) : patch(`/v1/admin/diet-tags/${id}`, { label }),

  deleteDietTag: (id: string): Promise<{ id: string }> =>
    demoMode ? demo({ id }) : del(`/v1/admin/diet-tags/${id}`),

  certifications: (): Promise<AdminCertificationOption[]> =>
    demoMode
      ? demo(DEMO_CERTIFICATIONS)
      : get<{ items: AdminCertificationOption[] }>("/v1/admin/certifications").then(
          (body) => body.items,
        ),

  createCertification: (name: string): Promise<AdminCertificationOption> =>
    demoMode
      ? demo({ id: `cert_demo_${Date.now()}`, name })
      : post("/v1/admin/certifications", { name }),

  updateCertification: (id: string, name: string): Promise<AdminCertificationOption> =>
    demoMode ? demo({ id, name }) : patch(`/v1/admin/certifications/${id}`, { name }),

  deleteCertification: (id: string): Promise<{ id: string }> =>
    demoMode ? demo({ id }) : del(`/v1/admin/certifications/${id}`),

  getCategory: (id: string): Promise<AdminCategoryDetail> => {
    if (!demoMode) return get<AdminCategoryDetail>(`/v1/admin/categories/${id}`);
    const category = adminCategories.find((entry) => entry.id === id);
    if (!category) throw new ApiError("Category not found.", 404, "not_found");
    return demo<AdminCategoryDetail>({
      id: category.id,
      name: category.name,
      slug: category.slug,
      shortDescription: "",
      heroEyebrow: "",
      heroTitle: category.name,
      heroDescription: "",
      seasonLabel: "",
      themeKey: "forest",
      visibility: category.visibility,
      status: category.status,
      seoTitle: "",
      seoDescription: "",
      indexingPolicy: "index",
      heroImageUrl: "",
      heroImageAlt: category.name,
      thumbnailImageUrl: "",
      thumbnailImageAlt: category.name,
      productAssignmentMode: "manual",
      releaseScope: "global",
      releaseCountries: [],
      updatedAt: category.updatedAt,
    });
  },

  createCategory: (input: {
    name: string;
    slug?: string;
    shortDescription?: string;
    heroTitle?: string;
    heroDescription?: string;
  }): Promise<{ id: string; slug: string; status: string }> =>
    demoMode
      ? demo({
          id: `cat_${Date.now().toString(36)}`,
          slug: input.slug ?? "new-category",
          status: "draft",
        })
      : post("/v1/admin/categories", input),

  updateCategory: (id: string, input: Record<string, unknown>): Promise<{ id: string }> =>
    demoMode ? demo({ id }) : patch(`/v1/admin/categories/${id}`, input),

  publishCategory: (id: string): Promise<{ status: string; version: number }> =>
    demoMode
      ? demo({ status: "published", version: 1 })
      : post(`/v1/admin/categories/${id}/publish`),

  updateCategoryStatus: (
    categoryId: string,
    status: "published" | "unpublished",
  ): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id: categoryId, status })
      : patch(`/v1/admin/categories/${categoryId}/status`, { status }),

  deleteCategory: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "archived" }) : del(`/v1/admin/categories/${id}`),

  deleteCategories: (categoryIds: string[]): Promise<{ deletedIds: string[]; count: number }> =>
    demoMode
      ? demo({ deletedIds: categoryIds, count: categoryIds.length })
      : post("/v1/admin/categories/bulk-delete", { categoryIds }),

  inventory: ({
    limit = 100,
    offset = 0,
    search,
  }: {
    limit?: number;
    offset?: number;
    search?: string;
  } = {}): Promise<AdminInventoryProductGroup[]> =>
    demoMode
      ? demo(groupInventoryByProduct(adminInventory))
      : get<{ items: AdminInventoryProductGroup[] }>(
          `/v1/admin/inventory?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  adjustInventory: (input: {
    variantId?: string;
    sku?: string;
    quantityDelta: number;
    reasonCode: string;
    note: string;
  }): Promise<{ onHand: number; available: number }> =>
    demoMode ? demo({ onHand: 0, available: 0 }) : post("/v1/admin/inventory/adjustments", input),

  clearInventory: (variantIds: string[]): Promise<{ clearedIds: string[]; count: number }> =>
    demoMode
      ? demo({ clearedIds: variantIds, count: variantIds.length })
      : post("/v1/admin/inventory/bulk-clear", {
          variantIds,
          note: "Bulk cleared from the admin inventory table.",
        }),

  orders: ({
    limit = 50,
    offset = 0,
    search,
  }: { limit?: number; offset?: number; search?: string } = {}): Promise<AdminOrderRow[]> =>
    demoMode
      ? demo(adminOrders)
      : get<{ items: AdminOrderRow[] }>(
          `/v1/admin/orders?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  getOrder: (id: string): Promise<AdminOrderDetail> => {
    if (!demoMode) return get<AdminOrderDetail>(`/v1/admin/orders/${id}`);
    const order = adminOrders.find((entry) => entry.id === id);
    if (!order) throw new ApiError("Order not found.", 404, "not_found");
    return demo<AdminOrderDetail>({
      id: order.id,
      publicReference: order.publicReference,
      customerEmail: order.customerEmail,
      currencyCode: order.currencyCode,
      subtotalMinor: order.totalMinor,
      discountMinor: 0,
      deliveryMinor: 0,
      taxMinor: 0,
      totalMinor: order.totalMinor,
      giftCardAppliedMinor: 0,
      giftCardCode: null,
      orderStatus: order.orderStatus,
      paymentStatus: order.paymentStatus,
      fulfilmentStatus: order.fulfilmentStatus,
      deliveryStatus: "not_ready",
      placedAt: order.placedAt,
      items: [],
      payment:
        order.paymentStatus === "not_required"
          ? null
          : {
              provider: "razorpay",
              status: order.paymentStatus,
              amountMinor: order.totalMinor,
              currencyCode: order.currencyCode,
              refundedMinor: 0,
            },
    });
  },

  updateOrderStatus: (id: string, status: string): Promise<{ orderStatus: string }> =>
    demoMode ? demo({ orderStatus: status }) : patch(`/v1/admin/orders/${id}/status`, { status }),

  refundOrder: (
    id: string,
    input: { amountMinor?: number; reason: string },
  ): Promise<{ paymentStatus: string; refundedMinor: number; totalRefundedMinor: number }> =>
    demoMode
      ? demo({
          paymentStatus: "refunded",
          refundedMinor: input.amountMinor ?? 0,
          totalRefundedMinor: input.amountMinor ?? 0,
        })
      : post(`/v1/admin/orders/${id}/refund`, input),

  refunds: ({ limit = 50, offset = 0 }: { limit?: number; offset?: number } = {}): Promise<
    AdminRefundRow[]
  > =>
    demoMode
      ? demo([])
      : get<{ items: AdminRefundRow[] }>(`/v1/admin/refunds?limit=${limit}&offset=${offset}`).then(
          (body) => body.items,
        ),

  users: ({
    limit = 50,
    offset = 0,
    search,
  }: { limit?: number; offset?: number; search?: string } = {}): Promise<AdminUserRow[]> =>
    demoMode
      ? demo(adminUsers)
      : get<{ items: AdminUserRow[] }>(
          `/v1/admin/users?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  roles: (): Promise<AdminRole[]> =>
    demoMode ? demo([]) : get<{ items: AdminRole[] }>("/v1/admin/roles").then((body) => body.items),

  permissions: (): Promise<AdminPermission[]> =>
    demoMode
      ? demo([])
      : get<{ items: AdminPermission[] }>("/v1/admin/permissions").then((body) => body.items),

  setRolePermissions: (
    id: string,
    permissionIds: string[],
  ): Promise<{ id: string; permissionIds: string[] }> =>
    demoMode
      ? demo({ id, permissionIds })
      : patch(`/v1/admin/roles/${id}/permissions`, { permissionIds }),

  createRole: (input: {
    name: string;
    description: string;
    permissionIds: string[];
  }): Promise<AdminRole> =>
    demoMode
      ? demo({
          id: `rol_${Date.now().toString(36)}`,
          key: input.name.toLowerCase().replace(/\s+/g, "-"),
          name: input.name,
          description: input.description,
          isSystem: false,
          locked: false,
          permissionIds: input.permissionIds,
          permissionKeys: [],
        })
      : post("/v1/admin/roles", input),

  updateRole: (
    id: string,
    input: { name: string; description: string },
  ): Promise<{ id: string; key: string; name: string; description: string }> =>
    demoMode
      ? demo({ id, key: id, name: input.name, description: input.description })
      : patch(`/v1/admin/roles/${id}`, input),

  deleteRole: (id: string): Promise<{ id: string; deleted: boolean }> =>
    demoMode ? demo({ id, deleted: true }) : del(`/v1/admin/roles/${id}`),

  inviteUser: (input: {
    email: string;
    displayName: string;
    roleIds: string[];
  }): Promise<{
    id: string;
    status: string;
    emailSent: boolean;
    emailTransport: EmailTransport;
  }> =>
    demoMode
      ? demo({
          id: `usr_${Date.now().toString(36)}`,
          status: "invited",
          emailSent: true,
          emailTransport: "console" as EmailTransport,
        })
      : post("/v1/admin/users/invite", input),

  createUser: (input: {
    email: string;
    displayName: string;
    roleIds: string[];
    password: string;
  }): Promise<{ id: string; email: string; status: string }> =>
    demoMode
      ? demo({ id: `usr_${Date.now().toString(36)}`, email: input.email, status: "active" })
      : post("/v1/admin/users", input),

  setUserStatus: (id: string, status: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status }) : patch(`/v1/admin/users/${id}/status`, { status }),

  setUserRoles: (id: string, roleIds: string[]): Promise<{ id: string }> =>
    demoMode ? demo({ id }) : patch(`/v1/admin/users/${id}/roles`, { roleIds }),

  deleteUser: (id: string): Promise<{ deletedIds: string[]; count: number }> =>
    demoMode ? demo({ deletedIds: [id], count: 1 }) : del(`/v1/admin/users/${id}`),

  deleteUsers: (userIds: string[]): Promise<{ deletedIds: string[]; count: number }> =>
    demoMode
      ? demo({ deletedIds: userIds, count: userIds.length })
      : post("/v1/admin/users/bulk-delete", { userIds }),

  sendUserPasswordReset: (
    id: string,
  ): Promise<{
    id: string;
    email: string;
    emailSent: boolean;
    emailTransport: EmailTransport;
  }> =>
    demoMode
      ? demo({
          id,
          email: "user@demo.test",
          emailSent: true,
          emailTransport: "console" as EmailTransport,
        })
      : post(`/v1/admin/users/${id}/password-reset-email`),

  contactMessages: ({
    limit = 50,
    offset = 0,
    search,
  }: {
    limit?: number;
    offset?: number;
    search?: string;
  } = {}): Promise<AdminContactMessageRow[]> =>
    demoMode
      ? demo([])
      : get<{ items: AdminContactMessageRow[] }>(
          `/v1/admin/contact-messages?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  farms: ({
    limit = 50,
    offset = 0,
    search,
  }: { limit?: number; offset?: number; search?: string } = {}): Promise<AdminFarmRow[]> =>
    demoMode
      ? demo([
          {
            id: "farm_devika",
            name: "Devika Organics",
            slug: "devika-organics",
            farmerName: "Devika Kulkarni",
            region: "Ratnagiri, Maharashtra",
            countryCode: "IN",
            establishedYear: 1998,
            summary: "Ratnagiri mango orchards farmed without synthetic chemicals.",
            status: "published",
            productCount: 1,
            updatedAt: "2026-07-01T00:00:00Z",
            heroImageUrl: null,
            heroImageAlt: null,
            indexingPolicy: "index",
          },
        ])
      : get<{ items: AdminFarmRow[] }>(
          `/v1/admin/farms?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  createFarm: (input: {
    name: string;
    slug?: string;
    farmerName: string;
    region: string;
    countryCode: string;
    establishedYear: number | null;
    summary: string;
    status: string;
    heroImageUrl?: string | null;
    heroImageAlt?: string | null;
    indexingPolicy?: "index" | "noindex";
  }): Promise<AdminFarmRow> =>
    demoMode
      ? demo({
          id: `farm_${Date.now().toString(36)}`,
          slug: input.slug || input.name.toLowerCase().replaceAll(" ", "-"),
          productCount: 0,
          updatedAt: new Date().toISOString(),
          heroImageUrl: null,
          heroImageAlt: null,
          indexingPolicy: "index",
          ...input,
        })
      : post("/v1/admin/farms", input),

  updateFarm: (
    id: string,
    input: {
      name: string;
      slug?: string;
      farmerName: string;
      region: string;
      countryCode: string;
      establishedYear: number | null;
      summary: string;
      status: string;
      heroImageUrl?: string | null;
      heroImageAlt?: string | null;
      indexingPolicy?: "index" | "noindex";
    },
  ): Promise<AdminFarmRow> =>
    demoMode
      ? demo({
          id,
          productCount: 0,
          updatedAt: new Date().toISOString(),
          heroImageUrl: null,
          heroImageAlt: null,
          indexingPolicy: "index",
          ...input,
          slug: input.slug || input.name.toLowerCase().replaceAll(" ", "-"),
        })
      : patch(`/v1/admin/farms/${id}`, input),

  deleteFarm: (
    id: string,
  ): Promise<{ id: string; status: string; archivedProductCount: number }> =>
    demoMode
      ? demo({ id, status: "archived", archivedProductCount: 0 })
      : del(`/v1/admin/farms/${id}`),

  createFarmOwner: (input: {
    email: string;
    displayName: string;
    farmId: string;
    password: string;
  }): Promise<{ id: string; farmName: string }> =>
    demoMode
      ? demo({ id: `usr_${Date.now().toString(36)}`, farmName: "Demo Farm" })
      : post("/v1/admin/farm-owners", input),

  changePassword: async (
    currentPassword: string,
    newPassword: string,
  ): Promise<{ ok: boolean }> => {
    if (demoMode) {
      await new Promise((resolve) => setTimeout(resolve, 180));
      if (currentPassword !== DEMO_PASSWORD) {
        throw new ApiError("Current password is incorrect.", 401, "authentication_required");
      }
      // Demo mode has no backend to store it — say so rather than pretend.
      throw new ApiError(
        "Demo mode cannot change a password. Connect the API with VITE_API_URL.",
        422,
        "validation_error",
      );
    }
    return post("/v1/admin/auth/change-password", { currentPassword, newPassword });
  },

  requestPasswordReset: (email: string): Promise<{ ok: boolean }> =>
    demoMode ? demo({ ok: true }) : post("/v1/admin/auth/password-reset", { email }),

  confirmPasswordReset: (token: string, newPassword: string): Promise<{ ok: boolean }> =>
    demoMode
      ? demo({ ok: true })
      : post("/v1/admin/auth/password-reset/confirm", { token, newPassword }),

  audit: ({ limit = 50, offset = 0 }: { limit?: number; offset?: number } = {}): Promise<
    AuditLogRow[]
  > =>
    demoMode
      ? demo(auditLog)
      : get<{ items: AuditLogRow[] }>(`/v1/admin/audit?limit=${limit}&offset=${offset}`).then(
          (body) => body.items,
        ),

  siteControl: (): Promise<SiteControl> =>
    demoMode
      ? demo({
          heroEyebrow: "Certified organic. Fully traceable.",
          heroHeading: "Food grown the way nature intended.",
          heroText: "Fresh organic produce, conscious pantry essentials and trusted local farms.",
          heroImageUrl: "/homepage-hero.png",
          heroImageAlt: "Organic mangoes held in a sunlit orchard",
          heroSlides: [
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
          primaryActionLabel: "Explore the market",
          primaryActionHref: "/shop",
          secondaryActionLabel: "See what is in season",
          secondaryActionHref: "/seasonal",
          seoTitle: "True Grit - traceable organic food from verified farms",
          seoDescription: "Fresh organic produce and trusted local farms.",
          seoKeywords: "organic food, traceable produce, Indian farms",
          featuredCategories: adminCategories.slice(0, 12).map((category) => category.slug),
          freshFavourites: products.slice(0, 4).map((p) => p.slug),
          heroMaxSlides: 12,
          heroSlidesHardLimit: 40,
        })
      : get<SiteControl>("/v1/admin/site-control"),

  updateSiteControl: (input: Partial<SiteControl>): Promise<SiteControl> =>
    demoMode ? demo(input as SiteControl) : patch("/v1/admin/site-control", input),

  announcements: (): Promise<AnnouncementsResponse> =>
    demoMode ? demo(demoAnnouncements()) : get<AnnouncementsResponse>("/v1/admin/announcements"),

  saveAnnouncement: (input: {
    scope: string;
    active: boolean;
    message: string;
    path: string;
  }): Promise<AnnouncementsResponse> => {
    if (!demoMode) return put("/v1/admin/announcements", input);
    const rows = demoAnnouncementRows();
    const index = rows.findIndex((row) => row.scope === input.scope);
    const saved: AnnouncementScopeRow = { ...input, updatedAt: new Date().toISOString() };
    if (index === -1) rows.push(saved);
    else rows[index] = saved;
    return demo(demoAnnouncements());
  },

  deleteAnnouncement: (scope: string): Promise<AnnouncementsResponse> => {
    if (!demoMode) return del(`/v1/admin/announcements/${encodeURIComponent(scope)}`);
    const rows = demoAnnouncementRows();
    const index = rows.findIndex((row) => row.scope === scope);
    if (index !== -1) rows.splice(index, 1);
    return demo(demoAnnouncements());
  },

  homepageSections: (): Promise<HomepageSectionsResponse> =>
    demoMode ? demo(demoSections()) : get<HomepageSectionsResponse>("/v1/admin/homepage/sections"),

  addHomepageSection: (type: string): Promise<HomepageSectionsResponse> => {
    if (!demoMode) return post("/v1/admin/homepage/sections", { type });
    const props = DEMO_NEW_SECTION_PROPS[type];
    if (!props) {
      throw new ApiError(`Cannot add a "${type}" section.`, 422, "validation_error");
    }
    demoBlocks().push({
      id: `blk_demo_${Date.now().toString(36)}`,
      type,
      version: 1,
      enabled: false,
      props: structuredClone(props),
    } as unknown as PublicPageBlock);
    return demo(demoSections());
  },

  updateHomepageSection: (
    sectionId: string,
    input: { enabled?: boolean; props?: Record<string, unknown> },
  ): Promise<HomepageSectionsResponse> => {
    if (!demoMode) {
      return patch(`/v1/admin/homepage/sections/${encodeURIComponent(sectionId)}`, input);
    }
    const blocks = demoBlocks();
    const block = blocks[demoSectionIndex(sectionId)]!;
    if (input.enabled !== undefined) block.enabled = input.enabled;
    if (input.props !== undefined) {
      block.props = structuredClone(input.props) as unknown as PublicPageBlock["props"];
    }
    return demo(demoSections());
  },

  deleteHomepageSection: (sectionId: string): Promise<HomepageSectionsResponse> => {
    if (!demoMode) return del(`/v1/admin/homepage/sections/${encodeURIComponent(sectionId)}`);
    demoBlocks().splice(demoSectionIndex(sectionId), 1);
    return demo(demoSections());
  },

  reorderHomepageSections: (ids: string[]): Promise<HomepageSectionsResponse> => {
    if (!demoMode) return post("/v1/admin/homepage/sections/order", { ids });
    const blocks = demoBlocks();
    const reordered = ids.map((id) => blocks[demoSectionIndex(id)]!);
    blocks.splice(0, blocks.length, ...reordered);
    return demo(demoSections());
  },

  homepageCountryOverrides: (): Promise<HomepageCountryOverridesResponse> =>
    demoMode
      ? demo({ overrides: structuredClone(demoHomepageOverrides()) })
      : get<HomepageCountryOverridesResponse>("/v1/admin/homepage/country-overrides"),

  setHomepageCountryOverride: (
    country: string,
    sectionId: string,
    enabled: boolean,
  ): Promise<HomepageCountryOverridesResponse> => {
    if (!demoMode) {
      return put(
        `/v1/admin/homepage/country-overrides/${encodeURIComponent(country)}/${encodeURIComponent(sectionId)}`,
        { enabled },
      );
    }
    demoSectionIndex(sectionId); // 404s for an unknown section, same as the API.
    const overrides = demoHomepageOverrides();
    overrides[country] ??= {};
    overrides[country]![sectionId] = enabled;
    return demo({ overrides: structuredClone(overrides) });
  },

  clearHomepageCountryOverride: (
    country: string,
    sectionId: string,
  ): Promise<HomepageCountryOverridesResponse> => {
    if (!demoMode) {
      return del(
        `/v1/admin/homepage/country-overrides/${encodeURIComponent(country)}/${encodeURIComponent(sectionId)}`,
      );
    }
    const overrides = demoHomepageOverrides();
    delete overrides[country]?.[sectionId];
    if (overrides[country] && Object.keys(overrides[country]!).length === 0) {
      delete overrides[country];
    }
    return demo({ overrides: structuredClone(overrides) });
  },

  priceAdjustments: (): Promise<PriceAdjustmentsResponse> =>
    demoMode
      ? demo(demoPriceAdjustments())
      : get<PriceAdjustmentsResponse>("/v1/admin/price-adjustments"),

  currencyRates: (): Promise<CurrencyRatesResponse> =>
    demoMode
      ? demo({
          baseCurrency: "INR" as const,
          rates: [
            {
              currencyCode: "INR",
              locale: "en-IN",
              ratePerInr: "1",
              active: true,
              updatedAt: new Date().toISOString(),
            },
            {
              currencyCode: "USD",
              locale: "en-US",
              ratePerInr: "0.0115",
              active: true,
              updatedAt: new Date().toISOString(),
            },
            {
              currencyCode: "EUR",
              locale: "en-IE",
              ratePerInr: "0.0105",
              active: true,
              updatedAt: new Date().toISOString(),
            },
          ],
        })
      : get<CurrencyRatesResponse>("/v1/admin/currency-rates"),

  saveCurrencyRate: (input: {
    currencyCode: string;
    locale: string;
    ratePerInr: string;
    active: boolean;
  }): Promise<{ rate: CurrencyRate }> =>
    demoMode
      ? demo({
          rate: {
            ...input,
            currencyCode: input.currencyCode.toUpperCase(),
            updatedAt: new Date().toISOString(),
          },
        })
      : put(`/v1/admin/currency-rates/${encodeURIComponent(input.currencyCode)}`, input),

  savePriceAdjustment: (input: {
    scope: string;
    productId?: string | null;
    categoryId?: string | null;
    percent: number;
    active: boolean;
  }): Promise<PriceAdjustmentsResponse> => {
    if (!demoMode) return put("/v1/admin/price-adjustments", input);
    const productId = input.productId ?? null;
    const categoryId = input.categoryId ?? null;
    if (productId && categoryId) {
      throw new ApiError(
        "A price adjustment can target one product or one category, not both.",
        422,
        "validation_error",
      );
    }
    const product = productId ? adminProducts.find((entry) => entry.id === productId) : null;
    if (productId && !product) {
      throw new ApiError("That product could not be found.", 404, "not_found");
    }
    const category = categoryId ? adminCategories.find((entry) => entry.id === categoryId) : null;
    if (categoryId && !category) {
      throw new ApiError("That category could not be found.", 404, "not_found");
    }

    const rules = demoPriceAdjustmentRows();
    const index = rules.findIndex(
      (rule) =>
        rule.scope === input.scope &&
        rule.productId === productId &&
        rule.categoryId === categoryId,
    );
    const saved: PriceAdjustmentRule = {
      id: index === -1 ? `padj_demo_${Date.now().toString(36)}` : rules[index]!.id,
      scope: input.scope,
      productId,
      productName: product?.name ?? null,
      productSlug: product?.slug ?? null,
      categoryId,
      categoryName: category?.name ?? null,
      categorySlug: category?.slug ?? null,
      percent: input.percent,
      active: input.active,
      updatedAt: new Date().toISOString(),
    };
    if (index === -1) rules.push(saved);
    else rules[index] = saved;
    return demo(demoPriceAdjustments());
  },

  deletePriceAdjustment: (ruleId: string): Promise<PriceAdjustmentsResponse> => {
    if (!demoMode) return del(`/v1/admin/price-adjustments/${encodeURIComponent(ruleId)}`);
    const rules = demoPriceAdjustmentRows();
    const index = rules.findIndex((rule) => rule.id === ruleId);
    if (index === -1) {
      throw new ApiError("That price adjustment rule could not be found.", 404, "not_found");
    }
    rules.splice(index, 1);
    return demo(demoPriceAdjustments());
  },

  appearance: (): Promise<AppearanceResponse> =>
    demoMode ? demo(demoAppearance()) : get<AppearanceResponse>("/v1/admin/appearance"),

  saveThemeScope: (scope: string, tokens: ThemeTokens): Promise<AppearanceResponse> => {
    if (!demoMode) return put("/v1/admin/appearance/theme", { scope, tokens });
    const bucket = demoThemeBucket(scope);
    if (scope === "global") demoAppearanceState().theme.global = { ...tokens };
    else if (Object.keys(tokens).length === 0) delete bucket[scope];
    else bucket[scope] = { ...tokens };
    return demo(demoAppearance());
  },

  deleteThemeScope: (scope: string): Promise<AppearanceResponse> => {
    if (!demoMode) {
      // Leading slash stripped: a doubled slash in the URL is not something a
      // caller should have to get right for a delete to work. A country scope
      // ("country:IN") has no leading slash to strip and passes through as-is.
      return del(`/v1/admin/appearance/theme/${scope.replace(/^\//, "")}`);
    }
    delete demoThemeBucket(scope)[scope];
    delete demoAppearanceState().countryEffects[scope];
    return demo(demoAppearance());
  },

  saveEffects: (
    effects: StorefrontEffects,
    scope: string = "global",
  ): Promise<AppearanceResponse> => {
    if (!demoMode) return put("/v1/admin/appearance/effects", { ...effects, scope });
    const state = demoAppearanceState();
    if (scope === "global") state.effects = structuredClone(effects);
    else state.countryEffects[scope] = structuredClone(effects);
    return demo(demoAppearance());
  },

  clearCountryEffects: (scope: string): Promise<AppearanceResponse> => {
    if (!demoMode) {
      return del(`/v1/admin/appearance/effects/${scope.replace(/^\//, "")}`);
    }
    delete demoAppearanceState().countryEffects[scope];
    return demo(demoAppearance());
  },

  siteDocuments: (): Promise<SiteDocuments> =>
    demoMode
      ? demo({
          robotsTxt:
            "User-agent: *\nAllow: /\nDisallow: /checkout\nDisallow: /account\nDisallow: /payment/\n\nSitemap: http://localhost:5173/sitemap.xml\n",
          sitemapXml:
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <url><loc>http://localhost:5173/</loc></url>\n</urlset>\n',
          llmsTxt:
            "# True Grit\n\nTraceable organic food from verified farms.\n\n## Core Pages\n- Home: http://localhost:5173/\n- Shop: http://localhost:5173/shop\n",
        })
      : get<SiteDocuments>("/v1/admin/site-documents"),

  updateSiteDocuments: (input: Partial<SiteDocuments>): Promise<SiteDocuments> =>
    demoMode ? demo(input as SiteDocuments) : patch("/v1/admin/site-documents", input),

  cmsPages: (): Promise<CmsPageRow[]> =>
    demoMode
      ? demo([
          {
            id: homePage.id,
            slug: homePage.slug,
            title: homePage.title,
            pageType: "landing",
            templateKey: "modular",
            status: "published",
            seoTitle: homePage.seo.title,
            seoDescription: homePage.seo.description,
            seoKeywords: homePage.seo.keywords ?? "",
            indexingPolicy: homePage.seo.indexing,
            updatedAt: new Date().toISOString(),
            blockCount: homePage.blocks.length,
          },
        ])
      : get<{ items: CmsPageRow[] }>("/v1/admin/pages").then((body) => body.items),

  cmsPage: (id: string): Promise<CmsPageDetail> =>
    demoMode
      ? demo({
          id: homePage.id,
          slug: homePage.slug,
          title: homePage.title,
          pageType: "landing",
          templateKey: "modular",
          status: "published",
          seoTitle: homePage.seo.title,
          seoDescription: homePage.seo.description,
          seoKeywords: homePage.seo.keywords ?? "",
          indexingPolicy: homePage.seo.indexing,
          updatedAt: new Date().toISOString(),
          blockCount: homePage.blocks.length,
          blocks: homePage.blocks,
        })
      : get<CmsPageDetail>(`/v1/admin/pages/${id}`),

  updateCmsPage: (
    id: string,
    input: Partial<CmsPageDetail> & { changeSummary?: string },
  ): Promise<CmsPageDetail> =>
    demoMode ? demo({ ...(input as CmsPageDetail), id }) : patch(`/v1/admin/pages/${id}`, input),

  // --- Per-locale page content (migration 0067) -------------------------
  //
  // The homepage and static pages both use `pages`/`page_versions`, so this
  // one mechanism translates both. Demo mode has no per-locale storage to
  // read, so it echoes the English content back untranslated rather than
  // pretending a translation exists.

  pageTranslations: (pageId: string): Promise<PageTranslationSummary[]> =>
    demoMode
      ? demo([])
      : get<{ items: PageTranslationSummary[] }>(`/v1/admin/pages/${pageId}/translations`).then(
          (body) => body.items,
        ),

  pageTranslation: (pageId: string, locale: string): Promise<PageTranslation> =>
    demoMode
      ? demo({
          locale,
          content: { blocks: homePage.blocks },
          autoTranslated: false,
          updatedAt: null,
        })
      : get<PageTranslation>(`/v1/admin/pages/${pageId}/translations/${locale}`),

  savePageTranslation: (
    pageId: string,
    locale: string,
    blocks: PublicPageBlock[],
  ): Promise<PageTranslation> =>
    demoMode
      ? demo({
          locale,
          content: { blocks },
          autoTranslated: false,
          updatedAt: new Date().toISOString(),
        })
      : put<PageTranslation>(`/v1/admin/pages/${pageId}/translations/${locale}`, { blocks }),

  autoTranslatePage: (pageId: string, locale: string): Promise<PageTranslation> =>
    demoMode
      ? Promise.reject(
          new ApiError(
            "Auto-translate needs the live API and a deployed Worker.",
            503,
            "demo_mode",
          ),
        )
      : post<PageTranslation>(
          `/v1/admin/pages/${pageId}/translations/${locale}/auto-translate`,
          {},
        ),

  deletePageTranslation: (
    pageId: string,
    locale: string,
  ): Promise<{ pageId: string; locale: string; deleted: boolean }> =>
    demoMode
      ? demo({ pageId, locale, deleted: true })
      : del(`/v1/admin/pages/${pageId}/translations/${locale}`),

  // --- Per-locale field overrides for other content types (migration 0068) -
  //
  // Same shape as the page translations above, generalized to flat fields
  // instead of a block tree: navigation labels, category/product names and
  // descriptions, article/recipe titles and excerpts. Demo mode echoes
  // English fields back untranslated, matching `pageTranslation` above.

  entityTranslations: (
    entityType: EntityTranslationType,
    entityId: string,
  ): Promise<EntityTranslationSummary[]> =>
    demoMode
      ? demo([])
      : get<{ items: EntityTranslationSummary[] }>(
          `/v1/admin/translations/${entityType}/${entityId}`,
        ).then((body) => body.items),

  entityTranslation: (
    entityType: EntityTranslationType,
    entityId: string,
    locale: string,
  ): Promise<EntityTranslation> =>
    demoMode
      ? demo({ locale, fields: {}, autoTranslated: false, updatedAt: null })
      : get<EntityTranslation>(`/v1/admin/translations/${entityType}/${entityId}/${locale}`),

  saveEntityTranslation: (
    entityType: EntityTranslationType,
    entityId: string,
    locale: string,
    fields: Record<string, string>,
  ): Promise<EntityTranslation> =>
    demoMode
      ? demo({ locale, fields, autoTranslated: false, updatedAt: new Date().toISOString() })
      : put<EntityTranslation>(`/v1/admin/translations/${entityType}/${entityId}/${locale}`, {
          fields,
        }),

  autoTranslateEntity: (
    entityType: EntityTranslationType,
    entityId: string,
    locale: string,
  ): Promise<EntityTranslation> =>
    demoMode
      ? Promise.reject(
          new ApiError(
            "Auto-translate needs the live API and a deployed Worker.",
            503,
            "demo_mode",
          ),
        )
      : post<EntityTranslation>(
          `/v1/admin/translations/${entityType}/${entityId}/${locale}/auto-translate`,
          {},
        ),

  deleteEntityTranslation: (
    entityType: EntityTranslationType,
    entityId: string,
    locale: string,
  ): Promise<{ entityType: string; entityId: string; locale: string; deleted: boolean }> =>
    demoMode
      ? demo({ entityType, entityId, locale, deleted: true })
      : del(`/v1/admin/translations/${entityType}/${entityId}/${locale}`),

  highlights: (): Promise<AdminLinkedProduct[]> =>
    demoMode
      ? demo(
          products
            .slice(0, 4)
            .map((p) => ({ id: p.id, name: p.name, slug: p.slug, status: "published" })),
        )
      : get<{ items: AdminLinkedProduct[] }>("/v1/admin/highlights").then((body) => body.items),

  setHighlights: (productIds: string[]): Promise<AdminLinkedProduct[]> =>
    demoMode
      ? demo(
          products
            .filter((p) => productIds.includes(p.id))
            .map((p) => ({ id: p.id, name: p.name, slug: p.slug, status: "published" })),
        )
      : put<{ items: AdminLinkedProduct[] }>("/v1/admin/highlights", { productIds }).then(
          (body) => body.items,
        ),

  uploadImage: async (
    file: File,
    resizeSpec?: Pick<ImageSpecification, "width" | "height">,
  ): Promise<{ id: string; url: string }> => {
    const upload = resizeSpec ? await resizeImageToSpec(file, resizeSpec) : file;
    return demoMode
      ? demo({ id: `img_${Date.now().toString(36)}`, url: URL.createObjectURL(upload) })
      : postFile(`/v1/admin/media/images?filename=${encodeURIComponent(upload.name)}`, upload);
  },

  homeBlocks: (): Promise<PublicPageBlock[]> => demo(homePage.blocks),

  // --- Articles (blog) -------------------------------------------------

  articles: ({
    limit = 25,
    offset = 0,
    search,
  }: { limit?: number; offset?: number; search?: string } = {}): Promise<AdminArticleRow[]> =>
    demoMode
      ? demo(
          demoArticles.map((article) => ({
            id: article.id,
            title: article.title,
            slug: article.slug,
            status: "published" as const,
            authorName: article.authorName,
            updatedAt: article.publishedAt,
            publishedAt: article.publishedAt,
            hasDraftChanges: false,
          })),
        )
      : get<{ items: AdminArticleRow[] }>(
          `/v1/admin/articles?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  getArticle: (id: string): Promise<AdminArticleDetail> => {
    if (!demoMode) return get<AdminArticleDetail>(`/v1/admin/articles/${id}`);
    const article = demoArticles.find((entry) => entry.id === id) ?? demoArticles[0]!;
    return demo<AdminArticleDetail>({
      id: article.id,
      title: article.title,
      slug: article.slug,
      excerpt: article.excerpt,
      readingMinutes: article.readingMinutes,
      status: "published",
      authorUserId: null,
      heroMediaId: null,
      heroImageUrl: article.heroImageUrl ?? "",
      heroImageAlt: article.heroImageAlt ?? "",
      seoTitle: article.seo.title,
      seoDescription: article.seo.description,
      seoKeywords: article.seo.keywords ?? "",
      canonicalUrl: article.seo.canonicalPath,
      indexingPolicy: article.seo.indexing,
      updatedAt: article.publishedAt,
      blocks: article.blocks,
      pullQuote: article.pullQuote,
    });
  },

  createArticle: (input: {
    title: string;
    slug?: string;
    excerpt?: string;
  }): Promise<{ id: string }> =>
    demoMode ? demo({ id: `art_${Date.now().toString(36)}` }) : post("/v1/admin/articles", input),

  updateArticle: (id: string, input: Record<string, unknown>): Promise<AdminArticleDetail> =>
    demoMode ? api.getArticle(id) : patch(`/v1/admin/articles/${id}`, input),

  submitArticle: (id: string): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: "in_review" })
      : post(`/v1/admin/articles/${id}/submit-for-review`),

  approveArticle: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "approved" }) : post(`/v1/admin/articles/${id}/approve`),

  requestArticleChanges: (id: string, note: string): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: "draft" })
      : post(`/v1/admin/articles/${id}/request-changes`, { note }),

  publishArticle: (id: string): Promise<{ id: string; status: string; version: number }> =>
    demoMode
      ? demo({ id, status: "published", version: 1 })
      : post(`/v1/admin/articles/${id}/publish`),

  unpublishArticle: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "unpublished" }) : post(`/v1/admin/articles/${id}/unpublish`),

  deleteArticle: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "archived" }) : del(`/v1/admin/articles/${id}`),

  deleteArticles: (articleIds: string[]): Promise<{ deletedIds: string[]; count: number }> =>
    demoMode
      ? demo({ deletedIds: articleIds, count: articleIds.length })
      : post("/v1/admin/articles/bulk-delete", { articleIds }),

  // --- Recipes -----------------------------------------------------------

  recipes: ({
    limit = 25,
    offset = 0,
    search,
  }: { limit?: number; offset?: number; search?: string } = {}): Promise<AdminRecipeRow[]> =>
    demoMode
      ? demo(
          demoRecipes.map((recipe) => ({
            id: recipe.id,
            title: recipe.title,
            slug: recipe.slug,
            status: "published" as const,
            chefName: "Demo Chef",
            updatedAt: new Date().toISOString(),
            publishedAt: new Date().toISOString(),
            hasDraftChanges: false,
          })),
        )
      : get<{ items: AdminRecipeRow[] }>(
          `/v1/admin/recipes?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  getRecipe: (id: string): Promise<AdminRecipeDetail> => {
    if (!demoMode) return get<AdminRecipeDetail>(`/v1/admin/recipes/${id}`);
    const recipe = demoRecipes.find((entry) => entry.id === id) ?? demoRecipes[0]!;
    return demo<AdminRecipeDetail>({
      id: recipe.id,
      title: recipe.title,
      slug: recipe.slug,
      excerpt: recipe.excerpt,
      prepMinutes: recipe.prepMinutes,
      cookMinutes: recipe.cookMinutes,
      servings: recipe.servings,
      dietaryTags: recipe.dietaryTags,
      status: "published",
      chefUserId: null,
      heroImageUrl: recipe.heroImageUrl ?? "",
      heroImageAlt: recipe.heroImageAlt ?? "",
      seoTitle: recipe.seo.title,
      seoDescription: recipe.seo.description,
      seoKeywords: recipe.seo.keywords ?? "",
      canonicalUrl: recipe.seo.canonicalPath,
      indexingPolicy: recipe.seo.indexing,
      updatedAt: new Date().toISOString(),
      blocks: recipe.blocks,
      steps: recipe.steps,
      ingredients: recipe.ingredients.map((ingredient, index) => ({
        id: `demo_ing_${index}`,
        label: ingredient.label,
        quantityText: ingredient.quantityText,
        productId: null,
        productSlug: ingredient.productSlug,
      })),
    });
  },

  createRecipe: (input: {
    title: string;
    slug?: string;
    excerpt?: string;
  }): Promise<{ id: string }> =>
    demoMode ? demo({ id: `rcp_${Date.now().toString(36)}` }) : post("/v1/admin/recipes", input),

  updateRecipe: (id: string, input: Record<string, unknown>): Promise<AdminRecipeDetail> =>
    demoMode ? api.getRecipe(id) : patch(`/v1/admin/recipes/${id}`, input),

  submitRecipe: (id: string): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: "in_review" })
      : post(`/v1/admin/recipes/${id}/submit-for-review`),

  approveRecipe: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "approved" }) : post(`/v1/admin/recipes/${id}/approve`),

  requestRecipeChanges: (id: string, note: string): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: "draft" })
      : post(`/v1/admin/recipes/${id}/request-changes`, { note }),

  publishRecipe: (id: string): Promise<{ id: string; status: string; version: number }> =>
    demoMode
      ? demo({ id, status: "published", version: 1 })
      : post(`/v1/admin/recipes/${id}/publish`),

  unpublishRecipe: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "unpublished" }) : post(`/v1/admin/recipes/${id}/unpublish`),

  deleteRecipe: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "archived" }) : del(`/v1/admin/recipes/${id}`),

  deleteRecipes: (recipeIds: string[]): Promise<{ deletedIds: string[]; count: number }> =>
    demoMode
      ? demo({ deletedIds: recipeIds, count: recipeIds.length })
      : post("/v1/admin/recipes/bulk-delete", { recipeIds }),

  // --- Return requests -----------------------------------------------------

  returns: ({
    status,
    limit = 50,
    offset = 0,
    search,
  }: {
    status?: string;
    limit?: number;
    offset?: number;
    search?: string;
  } = {}): Promise<AdminReturnRequestRow[]> =>
    demoMode
      ? demo([])
      : get<{ items: AdminReturnRequestRow[] }>(
          `/v1/admin/returns?limit=${limit}&offset=${offset}${status ? `&status=${encodeURIComponent(status)}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  getReturn: (id: string): Promise<AdminReturnRequestDetail> =>
    demoMode
      ? Promise.reject(new ApiError("Demo mode has no return requests yet.", 404, "not_found"))
      : get<AdminReturnRequestDetail>(`/v1/admin/returns/${id}`),

  decideReturn: (id: string, decision: string): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: decision })
      : post(`/v1/admin/returns/${id}/decide`, { decision }),

  resolveReturn: (
    id: string,
    input: {
      resolutionType: string;
      resolutionAmountMinor?: number | null;
      resolutionNotes?: string;
    },
  ): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "completed" }) : post(`/v1/admin/returns/${id}/resolve`, input),

  // --- Community blog/recipe submissions ------------------------------------

  submissions: ({
    contentType,
    status,
    limit = 50,
    offset = 0,
    search,
  }: {
    contentType?: string;
    status?: string;
    limit?: number;
    offset?: number;
    search?: string;
  } = {}): Promise<AdminSubmissionRow[]> =>
    demoMode
      ? demo([])
      : get<{ items: AdminSubmissionRow[] }>(
          `/v1/admin/submissions?limit=${limit}&offset=${offset}${contentType ? `&content_type=${encodeURIComponent(contentType)}` : ""}${status ? `&status=${encodeURIComponent(status)}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  submissionsPendingCount: (): Promise<number> =>
    demoMode
      ? demo(0)
      : get<{ count: number }>(`/v1/admin/submissions/pending-count`).then((body) => body.count),

  getSubmission: (id: string): Promise<AdminSubmissionDetail> =>
    demoMode
      ? Promise.reject(new ApiError("Demo mode has no submissions yet.", 404, "not_found"))
      : get<AdminSubmissionDetail>(`/v1/admin/submissions/${id}`),

  decideSubmission: (
    id: string,
    decision: string,
    note?: string,
  ): Promise<{ id: string; status: string; publishedId?: string; slug?: string }> =>
    demoMode
      ? demo({ id, status: decision })
      : post(`/v1/admin/submissions/${id}/decide`, { decision, note }),

  // --- Community discussions -------------------------------------------------

  discussions: ({
    status,
    limit = 50,
    offset = 0,
    search,
  }: {
    status?: string;
    limit?: number;
    offset?: number;
    search?: string;
  } = {}): Promise<AdminDiscussionRow[]> =>
    demoMode
      ? demo([])
      : get<{ items: AdminDiscussionRow[] }>(
          `/v1/admin/discussions?limit=${limit}&offset=${offset}${status ? `&status=${encodeURIComponent(status)}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  getDiscussion: (id: string): Promise<AdminDiscussionDetail> =>
    demoMode
      ? Promise.reject(new ApiError("Demo mode has no discussions yet.", 404, "not_found"))
      : get<AdminDiscussionDetail>(`/v1/admin/discussions/${id}`),

  moderateDiscussion: (
    id: string,
    action?: string,
    reason?: string,
    indexingPolicy?: "index" | "noindex",
  ): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: action ?? "visible" })
      : post(`/v1/admin/discussions/${id}/moderate`, { action, reason, indexingPolicy }),

  deleteDiscussion: (id: string): Promise<{ id: string; deleted: boolean }> =>
    demoMode ? demo({ id, deleted: true }) : del(`/v1/admin/discussions/${id}`),

  deleteDiscussions: (discussionIds: string[]): Promise<{ deletedIds: string[]; count: number }> =>
    demoMode
      ? demo({ deletedIds: discussionIds, count: discussionIds.length })
      : post("/v1/admin/discussions/bulk-delete", { discussionIds }),

  moderateComment: (
    commentId: string,
    action: string,
    reason?: string,
  ): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id: commentId, status: action })
      : post(`/v1/admin/discussions/comments/${commentId}/moderate`, { action, reason }),

  deleteComment: (commentId: string): Promise<{ id: string; deleted: boolean }> =>
    demoMode
      ? demo({ id: commentId, deleted: true })
      : del(`/v1/admin/discussions/comments/${commentId}`),

  // --- Reader comments on articles/recipes ------------------------------
  //
  // Policed with the same `discussions.*` permissions as community threads
  // (migration 0043) rather than a parallel grant.

  contentComments: ({
    contentType,
    status,
    limit = 50,
    offset = 0,
    search,
  }: {
    contentType?: string;
    status?: string;
    limit?: number;
    offset?: number;
    search?: string;
  } = {}): Promise<{ items: AdminContentCommentRow[]; total: number; enabled: boolean }> =>
    demoMode
      ? demo({ items: [], total: 0, enabled: true })
      : get<{ items: AdminContentCommentRow[]; total: number; enabled: boolean }>(
          `/v1/admin/content-comments?limit=${limit}&offset=${offset}${contentType ? `&content_type=${encodeURIComponent(contentType)}` : ""}${status ? `&status=${encodeURIComponent(status)}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ),

  moderateContentComment: (
    commentId: string,
    action: string,
    reason?: string,
  ): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id: commentId, status: action })
      : post(`/v1/admin/content-comments/${commentId}/moderate`, { action, reason }),

  deleteContentComment: (commentId: string): Promise<{ id: string; deleted: boolean }> =>
    demoMode
      ? demo({ id: commentId, deleted: true })
      : del(`/v1/admin/content-comments/${commentId}`),

  // --- Product reviews and ratings ---------------------------------------
  //
  // Policed with their own `reviews.*` pair (migration 0057), not the
  // `discussions.*` grant content_comments reuses -- reviews are
  // commerce-adjacent, not editorial-adjacent.

  reviews: ({
    status,
    rating,
    limit = 50,
    offset = 0,
    search,
  }: {
    status?: string;
    rating?: number;
    limit?: number;
    offset?: number;
    search?: string;
  } = {}): Promise<{ items: AdminReviewRow[]; total: number; pending: number }> =>
    demoMode
      ? demo({
          items: adminReviews,
          total: adminReviews.length,
          pending: adminReviews.filter((row) => row.status === "pending").length,
        })
      : get<{ items: AdminReviewRow[]; total: number; pending: number }>(
          `/v1/admin/reviews?limit=${limit}&offset=${offset}${status ? `&status=${encodeURIComponent(status)}` : ""}${rating ? `&rating=${rating}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ),

  reviewsPendingCount: (): Promise<number> =>
    demoMode
      ? demo(adminReviews.filter((row) => row.status === "pending").length)
      : get<{ items: AdminReviewRow[]; total: number; pending: number }>(
          `/v1/admin/reviews?status=pending&limit=1`,
        ).then((body) => body.pending),

  moderateReview: (
    reviewId: string,
    action: string,
    reason?: string,
  ): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id: reviewId, status: action })
      : post(`/v1/admin/reviews/${reviewId}/moderate`, { action, reason }),

  editReview: (
    reviewId: string,
    input: { rating?: number; title?: string | null; body?: string },
  ): Promise<{ id: string; rating: number; title: string | null; body: string }> =>
    demoMode
      ? demo({
          id: reviewId,
          rating: input.rating ?? 5,
          title: input.title ?? null,
          body: input.body ?? "",
        })
      : patch(`/v1/admin/reviews/${reviewId}`, input),

  deleteReview: (reviewId: string): Promise<{ id: string; deleted: boolean }> =>
    demoMode ? demo({ id: reviewId, deleted: true }) : del(`/v1/admin/reviews/${reviewId}`),

  // --- Coupons and promotions ---------------------------------------------
  //
  // A promotion with no coupons is automatic; one or more coupons make it
  // code-gated. The sitewide on/off switch lives with the other storefront
  // switches (`storefrontSettings`/`updateStorefrontSettings` above).

  promotions: ({
    status,
    search,
    limit = 50,
    offset = 0,
  }: {
    status?: string;
    search?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<{ items: AdminPromotionRow[]; total: number }> =>
    demoMode
      ? demo({ items: adminPromotions, total: adminPromotions.length })
      : get<{ items: AdminPromotionRow[]; total: number }>(
          `/v1/admin/promotions?limit=${limit}&offset=${offset}${status ? `&status=${encodeURIComponent(status)}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ),

  getPromotion: (promotionId: string): Promise<AdminPromotionDetail> => {
    if (!demoMode) return get<AdminPromotionDetail>(`/v1/admin/promotions/${promotionId}`);
    const promotion = adminPromotions.find((entry) => entry.id === promotionId);
    if (!promotion) throw new ApiError("Promotion not found.", 404, "not_found");
    return demo<AdminPromotionDetail>({
      ...promotion,
      rule: null,
      action: {
        actionType: "percentage_discount",
        valueBasisPoints: 1500,
        amountMinor: null,
        maximumDiscountMinor: null,
      },
      coupons: [
        {
          id: "cpn_demo_welcome15",
          code: featuredPromotionFixture.code ?? "WELCOME15",
          active: true,
          redemptionCount: 0,
          createdAt: promotion.createdAt,
        },
      ],
    });
  },

  createPromotion: (input: {
    name: string;
    headline?: string | null;
    description?: string | null;
    status: string;
    priority: number;
    startsAt?: string | null;
    endsAt?: string | null;
    stackingPolicy: string;
    usageLimitTotal?: number | null;
    usageLimitPerCustomer?: number | null;
    minSubtotalMinor?: number | null;
    actionType: string;
    valueBasisPoints?: number | null;
    amountMinor?: number | null;
    maximumDiscountMinor?: number | null;
  }): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id: `promo_demo_${Date.now().toString(36)}`, status: input.status })
      : post(`/v1/admin/promotions`, input),

  updatePromotion: (
    promotionId: string,
    input: Partial<{
      name: string;
      headline: string | null;
      description: string | null;
      status: string;
      priority: number;
      startsAt: string | null;
      endsAt: string | null;
      usageLimitTotal: number | null;
      usageLimitPerCustomer: number | null;
    }>,
  ): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id: promotionId, status: input.status ?? "active" })
      : patch(`/v1/admin/promotions/${promotionId}`, input),

  deletePromotion: (
    promotionId: string,
  ): Promise<{ id: string; status: string; deleted: boolean }> =>
    demoMode
      ? demo({ id: promotionId, status: "deleted", deleted: true })
      : del(`/v1/admin/promotions/${promotionId}`),

  createCoupon: (promotionId: string, code: string): Promise<{ id: string; code: string }> =>
    demoMode
      ? demo({ id: `cpn_demo_${Date.now().toString(36)}`, code: code.toUpperCase() })
      : post(`/v1/admin/promotions/${promotionId}/coupons`, { code }),

  deleteCoupon: (couponId: string): Promise<{ id: string; deleted: boolean }> =>
    demoMode ? demo({ id: couponId, deleted: true }) : del(`/v1/admin/coupons/${couponId}`),

  // --- Gift cards --------------------------------------------------------
  //
  // Balance is derived from gift_card_redemptions, never stored -- see
  // services.gift_cards' module docstring. The sitewide on/off switch is on
  // Site Settings, next to the other storefront switches, same pattern as
  // promotions above.

  giftCards: ({
    search,
    limit = 25,
    offset = 0,
  }: { search?: string; limit?: number; offset?: number } = {}): Promise<{
    items: AdminGiftCardRow[];
    total: number;
  }> =>
    demoMode
      ? demo({ items: DEMO_GIFT_CARDS, total: DEMO_GIFT_CARDS.length })
      : get<{ items: AdminGiftCardRow[]; total: number }>(
          `/v1/admin/gift-cards?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ),

  getGiftCard: (giftCardId: string): Promise<AdminGiftCardDetail> => {
    if (!demoMode) return get<AdminGiftCardDetail>(`/v1/admin/gift-cards/${giftCardId}`);
    const card = DEMO_GIFT_CARDS.find((entry) => entry.id === giftCardId);
    if (!card) throw new ApiError("Gift card not found.", 404, "not_found");
    return demo<AdminGiftCardDetail>({ ...card, redemptions: [] });
  },

  issueGiftCard: (input: {
    balanceMinor: number;
    issuedToEmail?: string | null;
    note?: string | null;
    expiresAt?: string | null;
    code?: string | null;
  }): Promise<{ id: string; code: string; balanceMinor: number }> =>
    demoMode
      ? demo({
          id: `gft_demo_${Date.now().toString(36)}`,
          code: input.code?.toUpperCase() || `DEMO${Date.now().toString(36).toUpperCase()}`,
          balanceMinor: input.balanceMinor,
        })
      : post(`/v1/admin/gift-cards`, input),

  cancelGiftCard: (giftCardId: string): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id: giftCardId, status: "cancelled" })
      : post(`/v1/admin/gift-cards/${giftCardId}/cancel`, {}),

  // --- Bundles ---------------------------------------------------------
  //
  // Curated sets of specific variants sold together at a flat price. The
  // discount is enforced server-side at checkout, not just displayed here --
  // see `services.bundles.resolve_bundle_discount`.

  bundles: ({
    status,
    limit = 50,
    offset = 0,
  }: {
    status?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<{ items: AdminBundleRow[]; total: number }> =>
    demoMode
      ? demo({ items: adminBundles, total: adminBundles.length })
      : get<{ items: AdminBundleRow[]; total: number }>(
          `/v1/admin/bundles?limit=${limit}&offset=${offset}${status ? `&status=${encodeURIComponent(status)}` : ""}`,
        ),

  getBundle: (bundleId: string): Promise<AdminBundleDetail> => {
    if (!demoMode) return get<AdminBundleDetail>(`/v1/admin/bundles/${bundleId}`);
    const bundle = adminBundleDetails[bundleId];
    if (!bundle) throw new ApiError("Bundle not found.", 404, "not_found");
    return demo<AdminBundleDetail>(bundle);
  },

  createBundle: (input: {
    name: string;
    slug?: string;
    description?: string | null;
    status: string;
    bundlePriceMinor: number;
    imageUrl?: string | null;
    imageAlt?: string | null;
  }): Promise<{ id: string; slug: string; status: string }> =>
    demoMode
      ? demo({
          id: `bndl_demo_${Date.now().toString(36)}`,
          slug: input.slug || input.name.toLowerCase().replaceAll(" ", "-"),
          status: input.status,
        })
      : post(`/v1/admin/bundles`, input),

  updateBundle: (
    bundleId: string,
    input: Partial<{
      name: string;
      slug: string;
      description: string | null;
      status: string;
      bundlePriceMinor: number;
      imageUrl: string | null;
      imageAlt: string | null;
    }>,
  ): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id: bundleId, status: input.status ?? "active" })
      : patch(`/v1/admin/bundles/${bundleId}`, input),

  deleteBundle: (bundleId: string): Promise<{ id: string; deleted: boolean }> =>
    demoMode ? demo({ id: bundleId, deleted: true }) : del(`/v1/admin/bundles/${bundleId}`),

  replaceProductImages: (
    productId: string,
    images: { imageUrl: string; imageAlt?: string }[],
  ): Promise<{ images: AdminProductImage[] }> =>
    demoMode
      ? demo({
          images: images.map((image, index) => ({
            id: `pimg_demo_${index}`,
            imageUrl: image.imageUrl,
            imageAlt: image.imageAlt ?? null,
          })),
        })
      : put(`/v1/admin/products/${productId}/images`, { images }),

  replaceBundleItems: (
    bundleId: string,
    items: { variantId: string; quantity: number }[],
  ): Promise<{ items: AdminBundleItem[] }> =>
    demoMode
      ? demo({ items: adminBundleDetails[bundleId]?.items ?? [] })
      : put(`/v1/admin/bundles/${bundleId}/items`, { items }),

  // --- Delivery charges ----------------------------------------------------
  //
  // Stored settings, not hardcoded constants -- a seasonal fee change or a
  // raised free-delivery bar is an admin edit, not a deploy.

  deliverySettings: (): Promise<{ feeMinor: number; freeThresholdMinor: number }> =>
    demoMode
      ? demo({ feeMinor: 4_900, freeThresholdMinor: 150_000 })
      : get(`/v1/admin/delivery-settings`),

  updateDeliverySettings: (input: {
    feeMinor: number;
    freeThresholdMinor: number;
  }): Promise<{ feeMinor: number; freeThresholdMinor: number }> =>
    demoMode ? demo(input) : patch(`/v1/admin/delivery-settings`, input),

  // --- Curated list size -----------------------------------------------
  //
  // The shared cap for Fresh Favourites, Featured Categories (Homepage
  // Settings) and Highlights (Site Control) -- one setting rather than
  // three, since all three are the same shape of feature.

  curatedSettings: (): Promise<{ maxItems: number }> =>
    demoMode ? demo({ maxItems: 12 }) : get(`/v1/admin/curated-settings`),

  updateCuratedSettings: (input: { maxItems: number }): Promise<{ maxItems: number }> =>
    demoMode ? demo(input) : patch(`/v1/admin/curated-settings`, input),

  // --- Subscriptions -----------------------------------------------------
  //
  // "Subscribe & Save" (migration 0064): off sitewide by default. These
  // routes are support/oversight -- pause, resume, cancel a customer's
  // subscription, and the renewal job's manual twin -- not creation:
  // subscriptions only ever start from the customer's own product-page
  // action.

  subscriptionSettings: (): Promise<{ discountPercent: number }> =>
    demoMode ? demo({ discountPercent: 5 }) : get(`/v1/admin/subscription-settings`),

  updateSubscriptionSettings: (input: { percent: number }): Promise<{ discountPercent: number }> =>
    demoMode
      ? demo({ discountPercent: input.percent })
      : patch(`/v1/admin/subscription-settings`, input),

  subscriptions: ({
    status,
    limit = 50,
    offset = 0,
  }: {
    status?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<{ items: SubscriptionRow[]; total: number }> =>
    demoMode
      ? demo({ items: adminSubscriptions, total: adminSubscriptions.length })
      : get<{ items: SubscriptionRow[]; total: number }>(
          `/v1/admin/subscriptions?limit=${limit}&offset=${offset}${status ? `&status=${encodeURIComponent(status)}` : ""}`,
        ),

  pauseSubscription: (subscriptionId: string): Promise<SubscriptionRow> =>
    demoMode
      ? demo({ ...adminSubscriptions[0]!, id: subscriptionId, status: "paused" as const })
      : post(`/v1/admin/subscriptions/${subscriptionId}/pause`, {}),

  resumeSubscription: (subscriptionId: string): Promise<SubscriptionRow> =>
    demoMode
      ? demo({ ...adminSubscriptions[0]!, id: subscriptionId, status: "active" as const })
      : post(`/v1/admin/subscriptions/${subscriptionId}/resume`, {}),

  cancelSubscription: (subscriptionId: string): Promise<SubscriptionRow> =>
    demoMode
      ? demo({ ...adminSubscriptions[0]!, id: subscriptionId, status: "cancelled" as const })
      : post(`/v1/admin/subscriptions/${subscriptionId}/cancel`, {}),

  runSubscriptionRenewals: (): Promise<{
    processed: number;
    succeeded: number;
    outcomes: { subscriptionId: string; orderId: string | null; skippedReason: string | null }[];
  }> =>
    demoMode
      ? demo({ processed: 0, succeeded: 0, outcomes: [] })
      : post(`/v1/admin/subscriptions/run-renewals`, {}),

  // --- Farm partnership applications -------------------------------------
  //
  // Growers apply from the storefront with no account required; staff with
  // `farm_requests.review` triage here. Approval records a decision only --
  // it does not create a `farms` row (migration 0044).

  farmRequests: ({
    status,
    limit = 50,
    offset = 0,
    search,
  }: {
    status?: string;
    limit?: number;
    offset?: number;
    search?: string;
  } = {}): Promise<{ items: AdminFarmRequestRow[]; total: number }> =>
    demoMode
      ? demo({ items: [], total: 0 })
      : get<{ items: AdminFarmRequestRow[]; total: number }>(
          `/v1/admin/farm-requests?limit=${limit}&offset=${offset}${status ? `&status=${encodeURIComponent(status)}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ),

  farmRequestsOpenCount: (): Promise<number> =>
    demoMode
      ? demo(0)
      : get<{ count: number }>("/v1/admin/farm-requests/open-count").then((body) => body.count),

  getFarmRequest: (id: string): Promise<AdminFarmRequestDetail> =>
    demoMode
      ? Promise.reject(new ApiError("Demo mode has no farm applications yet.", 404, "not_found"))
      : get<AdminFarmRequestDetail>(`/v1/admin/farm-requests/${id}`),

  decideFarmRequest: (
    id: string,
    decision: string,
    note?: string,
  ): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: decision })
      : post(`/v1/admin/farm-requests/${id}/decide`, { decision, note }),

  linkFarmRequestToFarm: (
    id: string,
    farmId: string,
  ): Promise<{ id: string; linkedFarmId: string }> =>
    demoMode
      ? demo({ id, linkedFarmId: farmId })
      : post(`/v1/admin/farm-requests/${id}/link-farm`, { farmId }),

  deleteFarmRequest: (id: string): Promise<{ id: string; deleted: boolean }> =>
    demoMode ? demo({ id, deleted: true }) : del(`/v1/admin/farm-requests/${id}`),

  communitySettings: (): Promise<CommunitySettings> =>
    demoMode
      ? demo({ minAccountAgeMonths: 6 })
      : get<CommunitySettings>(`/v1/admin/community-settings`),

  updateCommunitySettings: (minAccountAgeMonths: number): Promise<CommunitySettings> =>
    demoMode
      ? demo({ minAccountAgeMonths })
      : patch(`/v1/admin/community-settings`, { minAccountAgeMonths }),

  // --- Storefront feature switches -------------------------------------
  //
  // Sign-in methods, taking payments, and the blog banner. Demo mode answers
  // with everything on, matching the shipped defaults in migration 0040.

  storefrontSettings: (): Promise<StorefrontSettingsResponse> =>
    demoMode
      ? demo(DEMO_STOREFRONT_SETTINGS)
      : get<StorefrontSettingsResponse>(`/v1/admin/storefront-settings`),

  updateStorefrontSettings: (
    input: Partial<StorefrontSettings>,
  ): Promise<StorefrontSettingsResponse> =>
    demoMode
      ? demo({
          settings: { ...DEMO_STOREFRONT_SETTINGS.settings, ...input },
          effective: DEMO_STOREFRONT_SETTINGS.effective,
        })
      : patch(`/v1/admin/storefront-settings`, input),

  loyaltyAccounts: (): Promise<{ items: LoyaltyAccountRow[]; total: number }> =>
    demoMode
      ? demo({ items: [], total: 0 })
      : get<{ items: LoyaltyAccountRow[]; total: number }>("/v1/admin/loyalty/accounts"),
  adjustLoyalty: (input: {
    customerUserId: string;
    points: number;
    reason: string;
  }): Promise<{ balance: number }> =>
    demoMode ? demo({ balance: input.points }) : post("/v1/admin/loyalty/adjustments", input),

  pickupPoints: (): Promise<{ items: PickupPointRow[]; total: number }> =>
    demoMode
      ? demo({ items: [], total: 0 })
      : get<{ items: PickupPointRow[]; total: number }>("/v1/admin/pickup-points"),
  createPickupPoint: (input: {
    name: string;
    address: Record<string, string>;
    hours?: string;
  }): Promise<PickupPointRow> =>
    demoMode
      ? demo({
          id: crypto.randomUUID(),
          name: input.name,
          address: input.address,
          hours: input.hours ?? null,
          phone: null,
          status: "active",
        })
      : post("/v1/admin/pickup-points", input),
  updatePickupPoint: (id: string, input: Partial<PickupPointRow>): Promise<PickupPointRow> =>
    demoMode
      ? demo({ ...(input as PickupPointRow), id })
      : patch(`/v1/admin/pickup-points/${id}`, input),

  harvestWindows: (): Promise<{ items: HarvestWindowRow[]; total: number }> =>
    demoMode
      ? demo({ items: [], total: 0 })
      : get<{ items: HarvestWindowRow[]; total: number }>("/v1/admin/harvest-windows"),
  createHarvestWindow: (input: {
    productId: string;
    expectedStart: string;
    expectedEnd: string;
    title?: string;
    maxPreorders?: number;
  }): Promise<HarvestWindowRow> =>
    demoMode
      ? Promise.reject(new ApiError("Unavailable in demo mode.", 503, "demo_mode"))
      : post("/v1/admin/harvest-windows", input),
  updateHarvestWindow: (id: string, input: Partial<HarvestWindowRow>): Promise<HarvestWindowRow> =>
    demoMode
      ? demo({ ...(input as HarvestWindowRow), id })
      : patch(`/v1/admin/harvest-windows/${id}`, input),
  preorders: (): Promise<{ items: PreorderRow[]; total: number }> =>
    demoMode
      ? demo({ items: [], total: 0 })
      : get<{ items: PreorderRow[]; total: number }>("/v1/admin/preorders"),
  markHarvestReady: (windowId: string): Promise<{ updated: number }> =>
    demoMode ? demo({ updated: 0 }) : post(`/v1/admin/harvest-windows/${windowId}/ready`, {}),
  fulfillPreorder: (preorderId: string): Promise<PreorderRow> =>
    demoMode
      ? Promise.reject(new ApiError("Unavailable in demo mode.", 503, "demo_mode"))
      : post(`/v1/admin/preorders/${preorderId}/fulfill`, {}),

  deliveryZones: (): Promise<{ items: DeliveryZoneRow[]; total: number }> =>
    demoMode
      ? demo({ items: [], total: 0 })
      : get<{ items: DeliveryZoneRow[]; total: number }>("/v1/admin/delivery-zones"),
  createDeliveryZone: (input: {
    name: string;
    postalCodes: string[];
    feeOverrideMinor?: number;
    leadTimeHours: number;
  }): Promise<DeliveryZoneRow> =>
    demoMode
      ? Promise.reject(new ApiError("Unavailable in demo mode.", 503, "demo_mode"))
      : post("/v1/admin/delivery-zones", input),
  updateDeliveryZone: (id: string, input: Partial<DeliveryZoneRow>): Promise<DeliveryZoneRow> =>
    demoMode
      ? demo({ ...(input as DeliveryZoneRow), id })
      : patch(`/v1/admin/delivery-zones/${id}`, input),
  createDeliverySlot: (
    zoneId: string,
    input: { dayOfWeek: number; startTime: string; endTime: string; maxOrders: number },
  ): Promise<unknown> =>
    demoMode ? demo({}) : post(`/v1/admin/delivery-zones/${zoneId}/slots`, input),

  b2bAccounts: (): Promise<{ items: B2BAccountRow[]; total: number }> =>
    demoMode
      ? demo({ items: [], total: 0 })
      : get<{ items: B2BAccountRow[]; total: number }>("/v1/admin/b2b/accounts"),
  createB2BAccount: (input: {
    companyName: string;
    gstNumber?: string;
    contactEmail?: string;
    creditLimitMinor: number;
    paymentTermsDays: number;
  }): Promise<B2BAccountRow> =>
    demoMode
      ? Promise.reject(new ApiError("Unavailable in demo mode.", 503, "demo_mode"))
      : post("/v1/admin/b2b/accounts", input),
  updateB2BAccount: (id: string, input: Partial<B2BAccountRow>): Promise<B2BAccountRow> =>
    demoMode
      ? demo({ ...(input as B2BAccountRow), id })
      : patch(`/v1/admin/b2b/accounts/${id}`, input),
  createB2BPriceBreak: (input: {
    variantId: string;
    minQuantity: number;
    priceMinor: number;
  }): Promise<unknown> => (demoMode ? demo({}) : post("/v1/admin/b2b/price-breaks", input)),
  linkB2BUser: (accountId: string, userId: string): Promise<{ linked: boolean }> =>
    demoMode
      ? demo({ linked: true })
      : post(`/v1/admin/b2b/accounts/${accountId}/users`, { userId }),
  b2bInvoices: (): Promise<{ items: B2BInvoiceRow[]; total: number }> =>
    demoMode
      ? demo({ items: [], total: 0 })
      : get<{ items: B2BInvoiceRow[]; total: number }>("/v1/admin/b2b/invoices"),
  markB2BInvoicePaid: (invoiceId: string, paymentReference?: string): Promise<B2BInvoiceRow> =>
    demoMode
      ? Promise.reject(new ApiError("Unavailable in demo mode.", 503, "demo_mode"))
      : post(`/v1/admin/b2b/invoices/${invoiceId}/paid`, { paymentReference }),

  // --- Route SEO overrides ---------------------------------------------

  routeSeoList: (): Promise<AdminRouteSeo[]> =>
    demoMode
      ? demo([])
      : get<{ items: AdminRouteSeo[] }>(`/v1/admin/route-seo`).then((body) => body.items),

  updateRouteSeo: (input: {
    path: string;
    seoTitle?: string;
    seoDescription?: string;
    seoKeywords?: string;
    indexingPolicy: "index" | "noindex";
  }): Promise<AdminRouteSeo> =>
    demoMode
      ? demo({
          path: input.path,
          seoTitle: input.seoTitle ?? null,
          seoDescription: input.seoDescription ?? null,
          seoKeywords: input.seoKeywords ?? null,
          indexingPolicy: input.indexingPolicy,
          updatedAt: new Date().toISOString(),
        })
      : patch(`/v1/admin/route-seo`, input),

  // --- Media library ---------------------------------------------------

  mediaLibrary: ({
    limit = 60,
    offset = 0,
    search,
  }: { limit?: number; offset?: number; search?: string } = {}): Promise<AdminMediaAssetRow[]> =>
    demoMode
      ? demo([]) // Assume empty or mock for demo
      : get<{ items: AdminMediaAssetRow[] }>(
          `/v1/admin/media?limit=${limit}&offset=${offset}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
        ).then((body) => body.items),

  updateMediaAsset: (
    id: string,
    input: { altText?: string; caption?: string },
  ): Promise<AdminMediaAssetRow> =>
    demoMode
      ? demo({
          id,
          url: "",
          originalFilename: "",
          mimeType: "image/png",
          sizeBytes: 0,
          widthPx: null,
          heightPx: null,
          altText: input.altText ?? "",
          caption: input.caption ?? "",
          createdAt: new Date().toISOString(),
        })
      : patch(`/v1/admin/media/${id}`, input),

  deleteMediaAsset: (id: string): Promise<{ id: string; deleted: boolean }> =>
    demoMode ? demo({ id, deleted: true }) : del(`/v1/admin/media/${id}`),

  // --- Owner reports console --------------------------------------------

  reports: (): Promise<ReportDefinitionSummary[]> =>
    demoMode
      ? demo([])
      : get<{ items: ReportDefinitionSummary[] }>("/v1/admin/reports").then((body) => body.items),

  runReport: (id: string, filters: Record<string, string>): Promise<ReportRunResult> =>
    demoMode
      ? demo({ id, label: id, columns: [], rows: [] })
      : post(`/v1/admin/reports/${id}/run`, { filters }),

  // --- Analytics -----------------------------------------------------------
  //
  // A visual dashboard over a date range -- revenue, orders, top products,
  // order-status mix -- computed live from orders/order_items, never a
  // stored rollup.

  analyticsOverview: (input: { from?: string; to?: string } = {}): Promise<AnalyticsOverview> =>
    demoMode
      ? demo(analyticsOverview)
      : get<AnalyticsOverview>(
          `/v1/admin/analytics/overview${
            input.from && input.to
              ? `?from=${encodeURIComponent(input.from)}&to=${encodeURIComponent(input.to)}`
              : ""
          }`,
        ),

  // --- Farm revenue & payouts --------------------------------------------

  revenue: (): Promise<FarmRevenueSummary> =>
    demoMode ? demo(DEMO_REVENUE) : get<FarmRevenueSummary>("/v1/admin/revenue"),

  farmRevenue: (farmId: string): Promise<FarmRevenueDetail> =>
    demoMode
      ? demo(demoFarmRevenueDetail(farmId))
      : get<FarmRevenueDetail>(`/v1/admin/revenue/farms/${farmId}`),

  payouts: (limit = 100): Promise<FarmPayout[]> =>
    demoMode
      ? demo([])
      : get<{ items: FarmPayout[] }>(`/v1/admin/revenue/payouts?limit=${limit}`).then(
          (body) => body.items,
        ),

  setDefaultCommission: (percent: number): Promise<{ defaultCommissionBps: number }> =>
    demoMode
      ? demo({ defaultCommissionBps: Math.round(percent * 100) })
      : patch("/v1/admin/revenue/commission", { percent }),

  /** `percent: null` clears the farm's override and returns it to the house
   *  default — distinct from 0, which charges the farm nothing. */
  setFarmCommission: (
    farmId: string,
    percent: number | null,
  ): Promise<{ commissionBps: number; commissionSource: "farm" | "default" }> =>
    demoMode
      ? demo({
          commissionBps: percent === null ? 1500 : Math.round(percent * 100),
          commissionSource: percent === null ? ("default" as const) : ("farm" as const),
        })
      : patch(`/v1/admin/revenue/farms/${farmId}/commission`, { percent }),

  /** Records a payout settling every outstanding line for the farm. This does
   *  not move money — no disbursement rail is configured; the operator
   *  transfers out of band and files the reference. `expectedPayoutMinor` is
   *  the amount shown on screen, so a balance that moved underneath is
   *  rejected rather than silently paying a different number. */
  issueFarmPayout: (
    farmId: string,
    body: { reference: string; note: string; expectedPayoutMinor: number },
  ): Promise<FarmPayoutResult> =>
    demoMode
      ? Promise.reject(
          new ApiError("Payouts are disabled in demo mode.", 400, "demo_mode_read_only"),
        )
      : post(`/v1/admin/revenue/farms/${farmId}/payouts`, body),

  // --- Owner-only: server logs -------------------------------------------

  serverLogs: ({ limit = 50, offset = 0 }: { limit?: number; offset?: number } = {}): Promise<
    AdminServerLogRow[]
  > =>
    demoMode
      ? demo([])
      : get<{ items: AdminServerLogRow[] }>(
          `/v1/admin/server-logs?limit=${limit}&offset=${offset}`,
        ).then((body) => body.items),

  // --- Owner-only: read-only DB browser -----------------------------------

  dbBrowserTables: (): Promise<string[]> =>
    demoMode
      ? demo([])
      : get<{ items: string[] }>("/v1/admin/db-browser/tables").then((body) => body.items),

  dbBrowserTable: (
    tableName: string,
    { limit = 50, offset = 0 }: { limit?: number; offset?: number } = {},
  ): Promise<AdminDbBrowserTableData> =>
    demoMode
      ? demo({ columns: [], rows: [], limit, offset })
      : get(
          `/v1/admin/db-browser/tables/${encodeURIComponent(tableName)}?limit=${limit}&offset=${offset}`,
        ),

  // --- Category geo release ---------------------------------------------

  setCategoryRelease: (
    id: string,
    input: { releaseScope: "global" | "selected"; releaseCountries: string[] },
  ): Promise<{ id: string }> =>
    demoMode
      ? demo({ id })
      : patch(`/v1/admin/categories/${id}`, {
          releaseScope: input.releaseScope,
          releaseCountries: input.releaseCountries,
        }),

  // --- Staff messaging -----------------------------------------------------
  // Reads/writes here are ordinary REST; a just-sent message itself is
  // delivered live over the WebSocket from conversationSocketUrl (below), not
  // through this object. See truegrit_api/realtime/chat_room.py.

  listConversations: (): Promise<ConversationSummary[]> =>
    demoMode ? demo([]) : get<ConversationSummary[]>("/v1/admin/messages/conversations"),

  conversationHistory: (
    conversationId: string,
    { limit = 50, offset = 0 }: { limit?: number; offset?: number } = {},
  ): Promise<ConversationHistory> =>
    demoMode
      ? demo({ conversationId, messages: [], limit })
      : get(
          `/v1/admin/messages/conversations/${conversationId}/history?limit=${limit}&offset=${offset}`,
        ),

  markConversationRead: (
    conversationId: string,
    lastReadMessageId: string | null,
  ): Promise<{ conversationId: string; lastReadAt: string }> =>
    demoMode
      ? demo({ conversationId, lastReadAt: new Date().toISOString() })
      : post(`/v1/admin/messages/conversations/${conversationId}/read`, { lastReadMessageId }),

  // Membership management (create/rename/add/remove) is owner-only at the API
  // (auth.dependencies.require_owner) — these calls 403 for anyone else, which
  // the UI avoids by only offering them behind isSuperAdmin.

  createConversation: (input: {
    type: "group" | "direct";
    name?: string | null;
    participantUserIds: string[];
  }): Promise<{ id: string; type: "group" | "direct"; name: string | null; reused: boolean }> =>
    demoMode
      ? Promise.reject(new ApiError("Messaging needs the live API.", 501, "not_supported_in_demo"))
      : post("/v1/admin/messages/conversations", input),

  renameConversation: (
    conversationId: string,
    name: string,
  ): Promise<{ id: string; name: string }> =>
    demoMode
      ? Promise.reject(new ApiError("Messaging needs the live API.", 501, "not_supported_in_demo"))
      : patch(`/v1/admin/messages/conversations/${conversationId}`, { name }),

  addConversationParticipants: (
    conversationId: string,
    userIds: string[],
  ): Promise<{ id: string; addedUserIds: string[] }> =>
    demoMode
      ? Promise.reject(new ApiError("Messaging needs the live API.", 501, "not_supported_in_demo"))
      : post(`/v1/admin/messages/conversations/${conversationId}/participants`, { userIds }),

  removeConversationParticipant: (
    conversationId: string,
    userId: string,
  ): Promise<{ id: string; removedUserId: string }> =>
    demoMode
      ? Promise.reject(new ApiError("Messaging needs the live API.", 501, "not_supported_in_demo"))
      : del(`/v1/admin/messages/conversations/${conversationId}/participants/${userId}`),

  // Telegram-style translate: one message, or every currently-loaded message
  // in a conversation. Both are cached server-side on (messageId, locale), so
  // re-toggling the same target language never re-calls the translator.

  translateMessage: (
    conversationId: string,
    messageId: string,
    locale: string,
  ): Promise<{ messageId: string; locale: string; translated: string }> =>
    demoMode
      ? Promise.reject(new ApiError("Messaging needs the live API.", 501, "not_supported_in_demo"))
      : post(`/v1/admin/messages/conversations/${conversationId}/messages/${messageId}/translate`, {
          locale,
        }),

  translateConversation: (
    conversationId: string,
    locale: string,
    messageIds: string[],
  ): Promise<{ locale: string; messages: Array<{ messageId: string; translated: string }> }> =>
    demoMode
      ? Promise.reject(new ApiError("Messaging needs the live API.", 501, "not_supported_in_demo"))
      : post(`/v1/admin/messages/conversations/${conversationId}/translate`, {
          locale,
          messageIds,
        }),

  // --- Admin support bot ---------------------------------------------------
  // Open to any signed-in staff member (no permission gate) -- every
  // live-data tool it can call re-checks the caller's own permissions
  // independently server-side. Knowledge/settings management below is
  // `support_bot.manage`-gated.

  supportBotChat: (message: string, history: SupportBotChatTurn[]): Promise<{ reply: string }> =>
    demoMode
      ? demo({
          reply: "The support bot needs the live API to answer -- connect VITE_API_URL to try it.",
        })
      : post("/v1/admin/support-bot/chat", { message, history }),

  supportBotKnowledge: (scope?: SupportBotScope): Promise<SupportBotKnowledgeEntry[]> =>
    demoMode
      ? demo([])
      : get<SupportBotKnowledgeEntry[]>(
          `/v1/admin/support-bot/knowledge${scope ? `?scope=${scope}` : ""}`,
        ),

  createSupportBotKnowledge: (input: {
    scope: SupportBotScope;
    title: string;
    keywords: string;
    content: string;
  }): Promise<SupportBotKnowledgeEntry> =>
    demoMode
      ? Promise.reject(
          new ApiError("Knowledge base needs the live API.", 501, "not_supported_in_demo"),
        )
      : post("/v1/admin/support-bot/knowledge", input),

  updateSupportBotKnowledge: (
    entryId: string,
    input: { title: string; keywords: string; content: string },
  ): Promise<SupportBotKnowledgeEntry> =>
    demoMode
      ? Promise.reject(
          new ApiError("Knowledge base needs the live API.", 501, "not_supported_in_demo"),
        )
      : patch(`/v1/admin/support-bot/knowledge/${entryId}`, input),

  deleteSupportBotKnowledge: (entryId: string): Promise<{ id: string }> =>
    demoMode
      ? Promise.reject(
          new ApiError("Knowledge base needs the live API.", 501, "not_supported_in_demo"),
        )
      : del(`/v1/admin/support-bot/knowledge/${entryId}`),

  supportBotSettings: (): Promise<SupportBotSettings> =>
    demoMode
      ? demo({
          admin: true,
          storefront: true,
          historyTurns: 10,
          knowledgeSnippets: 6,
          searchResults: 5,
          policyChars: 4000,
          widgetColor: "",
          policyPages: "returns delivery help terms privacy standards about",
        })
      : get("/v1/admin/support-bot/settings"),

  setSupportBotEnabled: (
    scope: SupportBotScope,
    enabled: boolean,
  ): Promise<{ scope: SupportBotScope; enabled: boolean }> =>
    demoMode
      ? demo({ scope, enabled })
      : patch(`/v1/admin/support-bot/settings/${scope}`, { enabled }),

  /** The API clamps each key to its own range, so the value it returns is
   *  authoritative and may differ from the one sent. */
  setSupportBotTuning: (
    key: SupportBotTuningKey,
    value: number,
  ): Promise<{ key: SupportBotTuningKey; value: number }> =>
    demoMode ? demo({ key, value }) : patch(`/v1/admin/support-bot/tuning/${key}`, { value }),

  /** Space- or comma-separated slugs; the API normalises and returns them. */
  setSupportBotPolicyPages: (policyPages: string): Promise<{ policyPages: string }> =>
    demoMode ? demo({ policyPages }) : patch("/v1/admin/support-bot/policy-pages", { policyPages }),

  /** Blank clears the override and returns both widgets to the brand colour. */
  setSupportBotWidgetColor: (widgetColor: string): Promise<{ widgetColor: string }> =>
    demoMode ? demo({ widgetColor }) : patch("/v1/admin/support-bot/widget-color", { widgetColor }),

  /** Public, unauthenticated: the floating widget is shown to every staff
   *  member, but the settings endpoint above is `support_bot.manage`-gated. */
  supportBotWidgetColor: (): Promise<string> =>
    demoMode
      ? demo("")
      : get<{ supportBotColor?: string }>("/v1/public/settings").then(
          (body) => body.supportBotColor ?? "",
        ),
};

/** `wss://…/v1/admin/messages/realtime/{conversationId}` — the session cookie
 * rides along automatically (same-origin WebSocket handshake), same as every
 * other admin request. Only meaningful when `!demoMode`; callers gate on that. */
export function conversationSocketUrl(conversationId: string): string {
  const wsOrigin = (API_URL ?? "").replace(/^http/, "ws");
  return `${wsOrigin}/v1/admin/messages/realtime/${conversationId}`;
}

export type { ContentBlock };
