/**
 * Server-side data access for route loaders.
 *
 * With `PUBLIC_API_URL` set, loaders call the FastAPI public endpoints. In
 * demo-data mode they resolve the deterministic fixture catalogue so the full
 * storefront renders (and is testable) before Cloudflare resources exist.
 */

import type {
  ArticleDetail,
  CategorySummary,
  FarmDetail,
  FeaturedPromotion,
  FeaturedReview,
  ProductDetail,
  ProductFilters,
  ProductReview,
  ProductSummary,
  PublicBootstrap,
  PublicBundle,
  PublicCategoryPage,
  PublicPage,
  PublicPageBlock,
  RecipeDetail,
} from "@truegrit/contracts";
import type { LocaleDefinition } from "@truegrit/i18n";
import {
  articles,
  bootstrap,
  categories,
  farms,
  getCategoryPage,
  homePage,
  productSlugsForCategory,
  allApprovedReviews,
  products,
  publicBundles,
  recipes,
  resolveFeaturedPromotion,
  resolveFeaturedReviews,
  reviewsForProduct,
} from "@truegrit/contracts/fixtures";

import { DEFAULT_SITE_SETTINGS, normalizeSiteSettings, type SiteSettings } from "./site-settings";
import type { DiscussionDetail } from "./community";
import type { DisplayCurrency } from "./currency";

export interface CatalogueRuntime {
  apiUrl?: string;
  apiWorker?: {
    fetch: typeof fetch;
  };
}

export function catalogueRuntime(context: unknown): CatalogueRuntime {
  const env = (
    context as
      | { cloudflare?: { env?: { PUBLIC_API_URL?: string; API_WORKER?: { fetch: typeof fetch } } } }
      | undefined
  )?.cloudflare?.env;
  return {
    apiUrl: env?.PUBLIC_API_URL,
    apiWorker: env?.API_WORKER,
  };
}

function apiUrl(runtime?: CatalogueRuntime): string {
  return (runtime?.apiUrl || process.env.PUBLIC_API_URL || "").trim().replace(/\/+$/, "");
}

async function fromApi<T>(path: string, runtime?: CatalogueRuntime): Promise<T | null> {
  const baseUrl = apiUrl(runtime);
  if (!baseUrl) return null;
  try {
    const request = new Request(`${baseUrl}${path}`, {
      headers: { accept: "application/json" },
    });
    const response = runtime?.apiWorker
      ? await runtime.apiWorker.fetch(request)
      : await fetch(request);
    if (response.status === 404) return null;
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

/** Append `country=XX` so the API geo-locks the catalogue to the visitor's
 * country. Fixture mode has no release data, so no filtering happens there. */
function withCountry(path: string, country?: string): string {
  if (!country) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}country=${encodeURIComponent(country)}`;
}

/** Appends `?locale=` (or `&locale=` alongside an existing query string) --
 *  the request-scoped locale root.tsx already resolves (cookie, then
 *  Accept-Language, then the default), so a CMS page can serve its saved
 *  translation (migration 0067) without the client picking a language a
 *  second time. Omits English: it is what `content_json` already stores, so
 *  there is nothing for the API to swap in. */
function withLocale(path: string, locale?: string): string {
  if (!locale || locale === "en") return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}locale=${encodeURIComponent(locale)}`;
}

// List endpoints wrap their rows in `{ items }`. Fixture data is used only when
// no API is configured; API mode must not mask backend failures with stale demo
// catalogue content.
async function listFromApi<T>(
  path: string,
  fallback: T[],
  runtime?: CatalogueRuntime,
): Promise<T[]> {
  if (!apiUrl(runtime)) return fallback;
  const body = await fromApi<{ items: T[] }>(path, runtime);
  return body?.items ?? [];
}

export interface PaginatedContent<T> {
  items: T[];
  total: number;
}

/** Runtime languages added from lang.truegritin.com. The shipped 100-language
 * list is merged with these in the root loader, so an API outage never removes
 * a language a visitor already uses. */
export async function loadCustomLocales(runtime?: CatalogueRuntime): Promise<LocaleDefinition[]> {
  if (!apiUrl(runtime)) return [];
  const body = await fromApi<{
    items: Array<{
      code: string;
      nativeName: string;
      englishName: string;
      direction: "ltr" | "rtl";
      groupName: "indian" | "world";
    }>;
  }>("/v1/public/locales/custom", runtime);
  return (body?.items ?? []).map((entry) => ({
    code: entry.code,
    nativeName: entry.nativeName,
    englishName: entry.englishName,
    dir: entry.direction,
    group: entry.groupName,
  }));
}

/** Reviewed/machine runtime corrections for the storefront's own UI
 * catalogue. They overlay the generated files and therefore take effect on
 * the next request without a storefront rebuild. */
export async function loadInterfaceTranslations(
  locale: string,
  runtime?: CatalogueRuntime,
): Promise<Record<string, string>> {
  if (!apiUrl(runtime) || locale === "en") return {};
  const body = await fromApi<{ messages: Record<string, string> }>(
    `/v1/public/translations/interface?locale=${encodeURIComponent(locale)}`,
    runtime,
  );
  return body?.messages ?? {};
}

/** Active operator-managed display rates. Product and order values remain
 * canonical INR; these values only format geo-selected storefront prices. */
export async function loadCurrencyRates(
  runtime?: CatalogueRuntime,
): Promise<DisplayCurrency[] | null> {
  if (!apiUrl(runtime)) return null;
  const body = await fromApi<{
    rates: Array<{ currencyCode: string; locale: string; ratePerInr: string }>;
  }>("/v1/public/currency-rates", runtime);
  if (!body) return null;
  return body.rates
    .map((entry) => ({
      code: entry.currencyCode,
      locale: entry.locale,
      ratePerInr: Number(entry.ratePerInr),
    }))
    .filter((entry) => Number.isFinite(entry.ratePerInr) && entry.ratePerInr > 0);
}

async function paginatedFromApi<T>(
  path: string,
  fallback: T[],
  limit: number,
  offset: number,
  runtime?: CatalogueRuntime,
): Promise<PaginatedContent<T>> {
  if (!apiUrl(runtime)) {
    return { items: fallback.slice(offset, offset + limit), total: fallback.length };
  }
  const separator = path.includes("?") ? "&" : "?";
  const body = await fromApi<{ items: T[]; total: number }>(
    `${path}${separator}limit=${limit}&offset=${offset}`,
    runtime,
  );
  return { items: body?.items ?? [], total: body?.total ?? 0 };
}

export async function loadBootstrap(
  country: string | undefined,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<PublicBootstrap> {
  if (apiUrl(runtime)) {
    // `country` picks up a country-specific announcement over the site-wide
    // one, resolved server-side (`resolve_announcement`) — see the identical
    // pattern on `loadSiteSettings`. `locale` swaps in translated nav labels
    // (migration 0068) the same way `withLocale` already does for pages.
    return (
      (await fromApi<PublicBootstrap>(
        withLocale(withCountry("/v1/public/bootstrap", country), locale),
        runtime,
      )) ?? {
        navigation: [],
        footerNavigation: [],
        announcement: null,
      }
    );
  }
  return bootstrap;
}

/**
 * Owner-controlled switches for sign-in methods, taking payments, and the blog
 * banner. Loaded in the root loader so every route renders against the same
 * answer.
 *
 * An unreachable API (or demo-data mode) resolves to the shipped defaults, not
 * to "everything off": a settings fetch failing must not lock customers out of
 * a storefront that is otherwise working.
 */
export async function loadSiteSettings(
  country: string | undefined,
  runtime?: CatalogueRuntime,
): Promise<SiteSettings> {
  if (!apiUrl(runtime)) return DEFAULT_SITE_SETTINGS;
  // `country` folds in any per-country colour or effect override the owner
  // saved — a Diwali palette for visitors in India, snow only where it snows
  // — resolved server-side so the storefront itself stays unaware that
  // "global" was ever per-visitor.
  return normalizeSiteSettings(
    await fromApi<unknown>(withCountry("/v1/public/settings", country), runtime),
  );
}

export async function loadHome(
  country: string | undefined,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<PublicPage> {
  if (apiUrl(runtime)) {
    // `country` picks up this visitor's per-country section overrides
    // (`homepage_country_overrides`); `locale` picks up a saved translation
    // (migration 0067) if one exists for this page — the same "falls back
    // to the default, never breaks" pattern as country overrides.
    const path = withLocale(withCountry("/v1/public/home", country), locale);
    const page =
      (await fromApi<PublicPage>(path, runtime)) ??
      (await fromApi<PublicPage>(withLocale("/v1/public/pages/home", locale), runtime));
    if (!page) throw new Error("Homepage content is unavailable from the public API.");
    return page;
  }
  return homePage;
}

export async function loadPage(
  slug: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<PublicPage | null> {
  if (!apiUrl(runtime)) return slug === "home" ? homePage : null;
  return fromApi<PublicPage>(
    withLocale(`/v1/public/pages/${encodeURIComponent(slug)}`, locale),
    runtime,
  );
}

export interface RouteSeoOverride {
  path: string;
  seoTitle: string | null;
  seoDescription: string | null;
  seoKeywords: string | null;
  indexingPolicy: "index" | "noindex";
}

/** Admin-editable SEO for a route that has no single-segment CMS page record
 * (e.g. `/blog/submit`). Returns null when no override was saved — the
 * caller should fall back to its own hardcoded metadata, same as `loadPage`
 * falling back to `fallbackSeo`. */
export async function loadRouteSeo(
  path: string,
  runtime?: CatalogueRuntime,
): Promise<RouteSeoOverride | null> {
  if (!apiUrl(runtime)) return null;
  return fromApi<RouteSeoOverride>(
    `/v1/public/route-seo?path=${encodeURIComponent(path)}`,
    runtime,
  );
}

// Matches DEFAULT_PAGE_SIZE in apps/api/src/truegrit_api/api/public.py.
export const CATALOGUE_PAGE_SIZE = 24;

export async function loadCategoryPage(
  slug: string,
  country?: string,
  runtime?: CatalogueRuntime,
  page = 1,
  locale?: string,
): Promise<PublicCategoryPage | null> {
  const offset = (Math.max(page, 1) - 1) * CATALOGUE_PAGE_SIZE;
  if (apiUrl(runtime)) {
    const path = withLocale(
      withCountry(
        `/v1/public/categories/${slug}?limit=${CATALOGUE_PAGE_SIZE}&offset=${offset}`,
        country,
      ),
      locale,
    );
    return fromApi<PublicCategoryPage>(path, runtime);
  }
  return getCategoryPage(slug);
}

export async function loadCategories(
  country?: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<CategorySummary[]> {
  return listFromApi<CategorySummary>(
    withLocale(withCountry("/v1/public/categories", country), locale),
    categories,
    runtime,
  );
}

export async function loadAllProducts(
  country?: string,
  runtime?: CatalogueRuntime,
): Promise<ProductSummary[]> {
  return listFromApi<ProductSummary>(
    withCountry("/v1/public/products", country),
    products,
    runtime,
  );
}

/** Fixture vocabulary for the dietary/certification filters, mirroring
 * `database/seeds/development.sql` / migration 0081 -- used both as the
 * `/v1/public/filters` fallback and to best-effort filter the fixture
 * catalogue itself in demo mode (see `loadProductPage`). */
const DEMO_PRODUCT_FILTERS: ProductFilters = {
  dietTags: [
    { key: "vegan", label: "Vegan" },
    { key: "vegetarian", label: "Vegetarian" },
    { key: "gluten-free", label: "Gluten Free" },
    { key: "dairy-free", label: "Dairy Free" },
    { key: "nut-free", label: "Nut Free" },
    { key: "plant-based", label: "Plant Based" },
  ],
  certifications: [
    { slug: "india-organic", name: "India Organic (NPOP)" },
    { slug: "jaivik-bharat", name: "Jaivik Bharat" },
    { slug: "pgs-india", name: "PGS-India Green" },
  ],
};

/** The full dietary-tag and certification vocabulary for the shop grid's
 * filter checkboxes. */
export async function loadFilterFacets(runtime?: CatalogueRuntime): Promise<ProductFilters> {
  if (!apiUrl(runtime)) return DEMO_PRODUCT_FILTERS;
  const body = await fromApi<ProductFilters>("/v1/public/filters", runtime);
  return body ?? DEMO_PRODUCT_FILTERS;
}

/**
 * One page of the shop grid, optionally narrowed to a single category and/or
 * dietary tags / certifications.
 *
 * `categorySlug` is the shop page's in-place sidebar filter. The API resolves
 * an unknown or unpublished slug to an empty page rather than the full
 * catalogue, so a stale bookmark shows an empty state instead of silently
 * ignoring the filter — fixture mode matches that behaviour. `dietKeys`/
 * `certificationSlugs` are OR-within-facet (either match), AND-across-facets
 * (combined with `categorySlug` and with each other) — see
 * `tag_filter_clause`/`certification_filter_clause` in the API repository.
 */
export async function loadProductPage(
  page: number,
  country?: string,
  runtime?: CatalogueRuntime,
  categorySlug?: string | null,
  locale?: string,
  dietKeys?: string[],
  certificationSlugs?: string[],
): Promise<PaginatedContent<ProductSummary>> {
  const params = new URLSearchParams();
  if (categorySlug) params.set("category", categorySlug);
  if (dietKeys?.length) params.set("diet", dietKeys.join(","));
  if (certificationSlugs?.length) params.set("certification", certificationSlugs.join(","));
  const query = params.toString();
  const path = query ? `/v1/public/products?${query}` : "/v1/public/products";

  let fallback = categorySlug
    ? products.filter((product) => productSlugsForCategory(categorySlug).includes(product.slug))
    : products;
  // Fixture products carry tag/certification *labels*, not the keys/slugs
  // this function takes -- translate through the same fixed vocabulary
  // `/v1/public/filters` itself falls back to, so demo mode narrows results
  // too rather than silently ignoring these two filters.
  if (dietKeys?.length) {
    const wantedLabels = new Set(
      DEMO_PRODUCT_FILTERS.dietTags
        .filter((tag) => dietKeys.includes(tag.key))
        .map((tag) => tag.label),
    );
    fallback = fallback.filter((product) => product.tags.some((tag) => wantedLabels.has(tag)));
  }
  if (certificationSlugs?.length) {
    const wantedNames = new Set(
      DEMO_PRODUCT_FILTERS.certifications
        .filter((cert) => certificationSlugs.includes(cert.slug))
        .map((cert) => cert.name),
    );
    fallback = fallback.filter((product) =>
      product.certifications.some((name) => wantedNames.has(name)),
    );
  }

  return paginatedFromApi<ProductSummary>(
    withLocale(withCountry(path, country), locale),
    fallback,
    CATALOGUE_PAGE_SIZE,
    (Math.max(page, 1) - 1) * CATALOGUE_PAGE_SIZE,
    runtime,
  );
}

export async function loadProduct(
  slug: string,
  country?: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<ProductDetail | null> {
  if (apiUrl(runtime)) {
    return fromApi<ProductDetail>(
      withLocale(withCountry(`/v1/public/products/${slug}`, country), locale),
      runtime,
    );
  }
  return products.find((product) => product.slug === slug) ?? null;
}

export async function loadProductsBySlugs(
  slugs: string[],
  country?: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<ProductSummary[]> {
  if (slugs.length === 0) return [];
  if (apiUrl(runtime)) {
    const query = slugs.map((slug) => encodeURIComponent(slug)).join(",");
    return listFromApi<ProductSummary>(
      withLocale(withCountry(`/v1/public/products?slugs=${query}`, country), locale),
      [],
      runtime,
    );
  }
  const bySlug = new Map(products.map((product) => [product.slug, product]));
  return slugs.flatMap((slug) => bySlug.get(slug) ?? []);
}

/** Approved reviews for one product, newest first. */
export async function loadProductReviews(
  slug: string,
  runtime?: CatalogueRuntime,
): Promise<ProductReview[]> {
  return listFromApi<ProductReview>(
    `/v1/public/products/${encodeURIComponent(slug)}/reviews`,
    reviewsForProduct(slug),
    runtime,
  );
}

/** Every approved review sitewide, newest first -- backs the dedicated
 *  `/reviews` page. */
export async function loadAllReviews(
  page: number,
  pageSize: number,
  runtime?: CatalogueRuntime,
): Promise<PaginatedContent<FeaturedReview>> {
  return paginatedFromApi<FeaturedReview>(
    "/v1/public/reviews",
    allApprovedReviews,
    pageSize,
    (Math.max(page, 1) - 1) * pageSize,
    runtime,
  );
}

/**
 * Backs the homepage `reviews_showcase` block. `source: "manual"` fetches
 * exactly `reviewIds`, in order; `source: "rule"` fetches the current
 * top-rated approved reviews sitewide. Demo mode resolves the same shape from
 * the fixture reviews via `resolveFeaturedReviews`, so a block edited in
 * Homepage Settings previews correctly with no API configured.
 */
export async function loadFeaturedReviews(
  block: Extract<PublicPageBlock, { type: "reviews_showcase" }>,
  runtime?: CatalogueRuntime,
): Promise<FeaturedReview[]> {
  const { source, reviewIds, minRating, limit } = block.props;
  const manualIds = source === "manual" ? reviewIds : undefined;
  const query =
    manualIds && manualIds.length > 0
      ? `ids=${manualIds.map((id) => encodeURIComponent(id)).join(",")}`
      : `minRating=${minRating}&limit=${limit}`;
  return listFromApi<FeaturedReview>(
    `/v1/public/reviews/featured?${query}`,
    resolveFeaturedReviews({ reviewIds: manualIds, minRating, limit }),
    runtime,
  );
}

/**
 * Backs the homepage `promotion_banner` block and the checkout-page callout --
 * the same call, so the two never show hand-maintained versions of the same
 * offer. `source: "manual"` pins one specific promotion (re-validated
 * active/in-window server-side on every call); `source: "rule"` resolves the
 * current highest-priority automatic promotion. Returns `null` when the
 * sitewide switch is off or nothing currently qualifies -- an ordinary state,
 * rendered as nothing by the caller, the same as an empty reviews showcase.
 *
 * Demo mode has no `app_settings` row to consult, so it mirrors the API's own
 * default (migration 0060: off) via `DEFAULT_SITE_SETTINGS.promotions`,
 * rather than always showing the fixture promotion regardless of the switch.
 */
export async function loadFeaturedPromotion(
  promotionBlockProps: { source: "manual" | "rule"; promotionId: string | null },
  runtime?: CatalogueRuntime,
): Promise<FeaturedPromotion | null> {
  const { source, promotionId } = promotionBlockProps;
  if (!apiUrl(runtime)) {
    if (!DEFAULT_SITE_SETTINGS.promotions.enabled) return null;
    return resolveFeaturedPromotion({ promotionId: source === "manual" ? promotionId : null });
  }
  const query =
    source === "manual" && promotionId ? `?promotionId=${encodeURIComponent(promotionId)}` : "";
  const body = await fromApi<{ promotion: FeaturedPromotion | null }>(
    `/v1/public/promotions/featured${query}`,
    runtime,
  );
  return body?.promotion ?? null;
}

/**
 * Active, purchasable bundles for the shop. Each carries its own item list
 * and `savingsMinor`, computed server-side against current variant prices --
 * the same figure `resolve_bundle_discount` will actually grant at checkout,
 * so the shop card can never advertise more than checkout honours.
 */
export async function loadBundles(
  page: number,
  pageSize: number,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<PaginatedContent<PublicBundle>> {
  return paginatedFromApi<PublicBundle>(
    withLocale("/v1/public/bundles", locale),
    publicBundles,
    pageSize,
    (Math.max(page, 1) - 1) * pageSize,
    runtime,
  );
}

export async function loadBundle(
  slug: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<PublicBundle | null> {
  if (apiUrl(runtime)) {
    return fromApi<PublicBundle>(
      withLocale(`/v1/public/bundles/${encodeURIComponent(slug)}`, locale),
      runtime,
    );
  }
  return publicBundles.find((bundle) => bundle.slug === slug) ?? null;
}

/**
 * Real bestsellers -- ranked by quantity actually sold, never a curated
 * list. Backs the `recommendations` homepage block and the "you might also
 * like" rows woven into the basket, category, search and shop pages.
 * `excludeSlugs` drops products already shown elsewhere on the same page
 * (typically the basket's own line items).
 *
 * Demo mode has no order history to rank, so it resolves a deterministic
 * slice of the fixture catalogue instead -- gated on the same sitewide
 * switch (`DEFAULT_SITE_SETTINGS.recommendations`) the API itself checks, so
 * turning the feature off behaves identically with or without a backend.
 */
export async function loadBestsellers(
  {
    limit = 8,
    excludeSlugs,
    categorySlug,
  }: { limit?: number; excludeSlugs?: string[]; categorySlug?: string } = {},
  country?: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<ProductSummary[]> {
  if (!apiUrl(runtime)) {
    if (!DEFAULT_SITE_SETTINGS.recommendations.enabled) return [];
    const excluded = new Set(excludeSlugs ?? []);
    return products.filter((product) => !excluded.has(product.slug)).slice(0, limit);
  }
  const params = new URLSearchParams({ limit: String(limit) });
  if (excludeSlugs && excludeSlugs.length > 0) params.set("exclude", excludeSlugs.join(","));
  if (categorySlug) params.set("category", categorySlug);
  return listFromApi<ProductSummary>(
    withLocale(
      withCountry(`/v1/public/recommendations/bestsellers?${params.toString()}`, country),
      locale,
    ),
    [],
    runtime,
  );
}

/**
 * "Customers also bought" -- real co-purchase counts for one product, not a
 * curated "goes well with" list (that is `relatedSlugs`, a separate,
 * complementary signal). Empty for a product with no order history yet, or
 * in demo mode, which has no real orders to draw the signal from at all.
 */
export async function loadAlsoBought(
  slug: string,
  limit: number,
  country?: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<ProductSummary[]> {
  if (!apiUrl(runtime)) return [];
  return listFromApi<ProductSummary>(
    withLocale(
      withCountry(
        `/v1/public/products/${encodeURIComponent(slug)}/also-bought?limit=${limit}`,
        country,
      ),
      locale,
    ),
    [],
    runtime,
  );
}

/**
 * The owner-curated highlight slots (search page box). Curated in the admin's
 * Site Control; falls back to the first fixture products in demo mode so the
 * box is reviewable without the API.
 */
export async function loadHighlightedProducts(
  country?: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<ProductSummary[]> {
  return listFromApi<ProductSummary>(
    withLocale(withCountry("/v1/public/highlights", country), locale),
    products.slice(0, 4),
    runtime,
  );
}

export async function loadFarms(
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<FarmDetail[]> {
  return listFromApi<FarmDetail>(withLocale("/v1/public/farms", locale), farms, runtime);
}

export async function loadFarm(
  slug: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<FarmDetail | null> {
  if (apiUrl(runtime)) {
    return fromApi<FarmDetail>(
      withLocale(`/v1/public/farms/${encodeURIComponent(slug)}`, locale),
      runtime,
    );
  }
  return farms.find((farm) => farm.slug === slug) ?? null;
}

export async function loadRecipes(
  page: number,
  pageSize: number,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<PaginatedContent<RecipeDetail>> {
  return paginatedFromApi<RecipeDetail>(
    withLocale("/v1/public/recipes", locale),
    recipes,
    pageSize,
    (page - 1) * pageSize,
    runtime,
  );
}

export async function loadRecipe(
  slug: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<RecipeDetail | null> {
  if (apiUrl(runtime)) {
    return fromApi<RecipeDetail>(
      withLocale(`/v1/public/recipes/${encodeURIComponent(slug)}`, locale),
      runtime,
    );
  }
  return recipes.find((recipe) => recipe.slug === slug) ?? null;
}

export async function loadArticles(
  page: number,
  pageSize: number,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<PaginatedContent<ArticleDetail>> {
  return paginatedFromApi<ArticleDetail>(
    withLocale("/v1/public/articles", locale),
    articles,
    pageSize,
    (page - 1) * pageSize,
    runtime,
  );
}

export async function loadArticle(
  slug: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<ArticleDetail | null> {
  if (apiUrl(runtime)) {
    return fromApi<ArticleDetail>(
      withLocale(`/v1/public/articles/${encodeURIComponent(slug)}`, locale),
      runtime,
    );
  }
  return articles.find((article) => article.slug === slug) ?? null;
}

/** Community discussions have no fixture/demo mode (see `lib/community.ts`) —
 * live user-generated content, not catalogue data — so this is a thin
 * pass-through to the public API; `fromApi` already resolves to `null` when
 * no API is configured, same as every other loader here. */
export async function loadDiscussion(
  id: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<DiscussionDetail | null> {
  return fromApi<DiscussionDetail>(
    withLocale(`/v1/public/community/discussions/${encodeURIComponent(id)}`, locale),
    runtime,
  );
}

export async function loadSiteDocument(
  key: "robots_txt" | "sitemap_xml" | "llms_txt",
  runtime?: CatalogueRuntime,
): Promise<{ content: string; contentType: string } | null> {
  if (!apiUrl(runtime)) return null;
  const body = await fromApi<{ content: string; contentType: string }>(
    `/v1/public/site-documents/${key}`,
    runtime,
  );
  return body ? { content: body.content, contentType: body.contentType } : null;
}

export type SitemapKind =
  "products" | "categories" | "pages" | "blog" | "recipes" | "farms" | "discussions";

const EMPTY_URLSET =
  '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n</urlset>\n';

/** Per-type sitemap XML, always mechanically generated from live D1 content —
 * unlike `sitemap_xml` (the index), there is no owner-override path here, so
 * these can never go stale. Raw XML, not JSON, so this bypasses `fromApi`.
 *
 * `null` means "the API did not answer", which is deliberately distinct from
 * an empty urlset. A 200 carrying zero URLs is an authoritative statement that
 * the section has no pages, and a crawler acting on it drops URLs it already
 * knows about; a 5xx just tells it to come back later. Callers must not
 * collapse the two — see the `sitemaps.*.xml` routes. */
export async function loadSitemapXml(
  kind: SitemapKind,
  runtime?: CatalogueRuntime,
): Promise<string | null> {
  const baseUrl = apiUrl(runtime);
  // Demo-data mode has no backing catalogue to enumerate. Honest and stable:
  // there is genuinely nothing to list, so an empty urlset is the true answer.
  if (!baseUrl) return EMPTY_URLSET;
  try {
    const request = new Request(`${baseUrl}/v1/public/sitemaps/${kind}`, {
      headers: { accept: "application/xml" },
    });
    const response = runtime?.apiWorker
      ? await runtime.apiWorker.fetch(request)
      : await fetch(request);
    if (!response.ok) return null;
    return await response.text();
  } catch {
    return null;
  }
}

/** Shared response builder for the seven `/sitemaps/*.xml` routes. */
export async function sitemapResponse(
  kind: SitemapKind,
  runtime?: CatalogueRuntime,
): Promise<Response> {
  const xml = await loadSitemapXml(kind, runtime);
  if (xml === null) {
    return new Response("Sitemap temporarily unavailable.", {
      status: 503,
      headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
    });
  }
  return new Response(xml, {
    headers: {
      "content-type": "application/xml; charset=utf-8",
      "cache-control": "public, max-age=300",
    },
  });
}

export interface SearchGroups {
  query: string;
  total: number;
  groups: Array<{
    group: string;
    items: Array<{ id: string; name: string; path: string; slug?: string }>;
  }>;
}

export async function runSearch(
  query: string,
  country?: string,
  runtime?: CatalogueRuntime,
  locale?: string,
): Promise<SearchGroups> {
  if (apiUrl(runtime)) {
    const result = await fromApi<SearchGroups>(
      withLocale(withCountry(`/v1/public/search?q=${encodeURIComponent(query)}`, country), locale),
      runtime,
    );
    return result ?? { query, total: 0, groups: [] };
  }
  const needle = query.trim().toLowerCase();
  if (needle.length < 2) return { query, total: 0, groups: [] };

  const synonyms: Record<string, string> = {
    "finger millet": "ragi",
    "kidney beans": "rajma",
    peanut: "groundnut",
  };
  const expanded = [needle, synonyms[needle] ?? ""].filter(Boolean);
  const matches = (text: string) => expanded.some((term) => text.toLowerCase().includes(term));

  const groups: SearchGroups["groups"] = [];
  const productItems = products
    .filter((product) => matches(`${product.name} ${product.tags.join(" ")} ${product.farmName}`))
    .map((product) => ({
      id: product.id,
      name: product.name,
      slug: product.slug,
      path: `/product/${product.slug}`,
    }));
  if (productItems.length) groups.push({ group: "products", items: productItems });

  const farmItems = farms
    .filter((farm) => matches(`${farm.name} ${farm.region}`))
    .map((farm) => ({ id: farm.id, name: farm.name, path: `/farms/${farm.slug}` }));
  if (farmItems.length) groups.push({ group: "farms", items: farmItems });

  const recipeItems = recipes
    .filter((recipe) => matches(recipe.title))
    .map((recipe) => ({ id: recipe.id, name: recipe.title, path: `/recipes/${recipe.slug}` }));
  if (recipeItems.length) groups.push({ group: "recipes", items: recipeItems });

  const articleItems = articles
    .filter((article) => matches(article.title))
    .map((article) => ({ id: article.id, name: article.title, path: `/blog/${article.slug}` }));
  if (articleItems.length) groups.push({ group: "articles", items: articleItems });

  return {
    query,
    total: groups.reduce((sum, group) => sum + group.items.length, 0),
    groups,
  };
}
