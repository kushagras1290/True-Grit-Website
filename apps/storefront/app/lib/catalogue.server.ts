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
  ProductDetail,
  ProductSummary,
  PublicBootstrap,
  PublicCategoryPage,
  PublicPage,
  RecipeDetail,
} from "@truegrit/contracts";
import {
  articles,
  bootstrap,
  categories,
  farms,
  getCategoryPage,
  homePage,
  productSlugsForCategory,
  products,
  recipes,
} from "@truegrit/contracts/fixtures";

import { DEFAULT_SITE_SETTINGS, normalizeSiteSettings, type SiteSettings } from "./site-settings";

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

export async function loadBootstrap(runtime?: CatalogueRuntime): Promise<PublicBootstrap> {
  if (apiUrl(runtime)) {
    return (
      (await fromApi<PublicBootstrap>("/v1/public/bootstrap", runtime)) ?? {
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
export async function loadSiteSettings(runtime?: CatalogueRuntime): Promise<SiteSettings> {
  if (!apiUrl(runtime)) return DEFAULT_SITE_SETTINGS;
  return normalizeSiteSettings(await fromApi<unknown>("/v1/public/settings", runtime));
}

export async function loadHome(runtime?: CatalogueRuntime): Promise<PublicPage> {
  if (apiUrl(runtime)) {
    const page =
      (await fromApi<PublicPage>("/v1/public/home", runtime)) ??
      (await fromApi<PublicPage>("/v1/public/pages/home", runtime));
    if (!page) throw new Error("Homepage content is unavailable from the public API.");
    return page;
  }
  return homePage;
}

export async function loadPage(
  slug: string,
  runtime?: CatalogueRuntime,
): Promise<PublicPage | null> {
  if (!apiUrl(runtime)) return slug === "home" ? homePage : null;
  return fromApi<PublicPage>(`/v1/public/pages/${encodeURIComponent(slug)}`, runtime);
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
): Promise<PublicCategoryPage | null> {
  const offset = (Math.max(page, 1) - 1) * CATALOGUE_PAGE_SIZE;
  if (apiUrl(runtime)) {
    const path = withCountry(
      `/v1/public/categories/${slug}?limit=${CATALOGUE_PAGE_SIZE}&offset=${offset}`,
      country,
    );
    return fromApi<PublicCategoryPage>(path, runtime);
  }
  return getCategoryPage(slug);
}

export async function loadCategories(
  country?: string,
  runtime?: CatalogueRuntime,
): Promise<CategorySummary[]> {
  return listFromApi<CategorySummary>(
    withCountry("/v1/public/categories", country),
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

/**
 * One page of the shop grid, optionally narrowed to a single category.
 *
 * `categorySlug` is the shop page's in-place sidebar filter. The API resolves
 * an unknown or unpublished slug to an empty page rather than the full
 * catalogue, so a stale bookmark shows an empty state instead of silently
 * ignoring the filter — fixture mode matches that behaviour.
 */
export async function loadProductPage(
  page: number,
  country?: string,
  runtime?: CatalogueRuntime,
  categorySlug?: string | null,
): Promise<PaginatedContent<ProductSummary>> {
  const path = categorySlug
    ? `/v1/public/products?category=${encodeURIComponent(categorySlug)}`
    : "/v1/public/products";
  const fallback = categorySlug
    ? products.filter((product) => productSlugsForCategory(categorySlug).includes(product.slug))
    : products;
  return paginatedFromApi<ProductSummary>(
    withCountry(path, country),
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
): Promise<ProductDetail | null> {
  if (apiUrl(runtime)) {
    return fromApi<ProductDetail>(withCountry(`/v1/public/products/${slug}`, country), runtime);
  }
  return products.find((product) => product.slug === slug) ?? null;
}

/**
 * Full product details (variants included) for a handful of slugs — the recipe
 * "add every ingredient to cart" flow needs each variant, which the summary list
 * omits. Fetched in parallel; unknown slugs drop out. Reserve for the small,
 * bounded slug sets a single page references, not for grids.
 */
export async function loadProductDetailsBySlugs(
  slugs: string[],
  country?: string,
  runtime?: CatalogueRuntime,
): Promise<ProductDetail[]> {
  if (slugs.length === 0) return [];
  const details = await Promise.all(slugs.map((slug) => loadProduct(slug, country, runtime)));
  return details.filter((product): product is ProductDetail => product !== null);
}

export async function loadProductsBySlugs(
  slugs: string[],
  country?: string,
  runtime?: CatalogueRuntime,
): Promise<ProductSummary[]> {
  if (slugs.length === 0) return [];
  if (apiUrl(runtime)) {
    const query = slugs.map((slug) => encodeURIComponent(slug)).join(",");
    return listFromApi<ProductSummary>(
      withCountry(`/v1/public/products?slugs=${query}`, country),
      [],
      runtime,
    );
  }
  const bySlug = new Map(products.map((product) => [product.slug, product]));
  return slugs.flatMap((slug) => bySlug.get(slug) ?? []);
}

/**
 * The owner-curated highlight slots (search page box). Curated in the admin's
 * Site Control; falls back to the first fixture products in demo mode so the
 * box is reviewable without the API.
 */
export async function loadHighlightedProducts(
  country?: string,
  runtime?: CatalogueRuntime,
): Promise<ProductSummary[]> {
  return listFromApi<ProductSummary>(
    withCountry("/v1/public/highlights", country),
    products.slice(0, 4),
    runtime,
  );
}

export async function loadFarms(runtime?: CatalogueRuntime): Promise<FarmDetail[]> {
  return listFromApi<FarmDetail>("/v1/public/farms", farms, runtime);
}

export async function loadFarm(
  slug: string,
  runtime?: CatalogueRuntime,
): Promise<FarmDetail | null> {
  if (apiUrl(runtime)) {
    return fromApi<FarmDetail>(`/v1/public/farms/${encodeURIComponent(slug)}`, runtime);
  }
  return farms.find((farm) => farm.slug === slug) ?? null;
}

export async function loadRecipes(
  page: number,
  pageSize: number,
  runtime?: CatalogueRuntime,
): Promise<PaginatedContent<RecipeDetail>> {
  return paginatedFromApi<RecipeDetail>(
    "/v1/public/recipes",
    recipes,
    pageSize,
    (page - 1) * pageSize,
    runtime,
  );
}

export async function loadRecipe(
  slug: string,
  runtime?: CatalogueRuntime,
): Promise<RecipeDetail | null> {
  if (apiUrl(runtime)) {
    return fromApi<RecipeDetail>(`/v1/public/recipes/${encodeURIComponent(slug)}`, runtime);
  }
  return recipes.find((recipe) => recipe.slug === slug) ?? null;
}

export async function loadArticles(
  page: number,
  pageSize: number,
  runtime?: CatalogueRuntime,
): Promise<PaginatedContent<ArticleDetail>> {
  return paginatedFromApi<ArticleDetail>(
    "/v1/public/articles",
    articles,
    pageSize,
    (page - 1) * pageSize,
    runtime,
  );
}

export async function loadArticle(
  slug: string,
  runtime?: CatalogueRuntime,
): Promise<ArticleDetail | null> {
  if (apiUrl(runtime)) {
    return fromApi<ArticleDetail>(`/v1/public/articles/${encodeURIComponent(slug)}`, runtime);
  }
  return articles.find((article) => article.slug === slug) ?? null;
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

/** Per-type sitemap XML, always mechanically generated from live D1 content —
 * unlike `sitemap_xml` (the index), there is no owner-override path here, so
 * these can never go stale. Raw XML, not JSON, so this bypasses `fromApi`. */
export async function loadSitemapXml(
  kind: SitemapKind,
  runtime?: CatalogueRuntime,
): Promise<string> {
  const baseUrl = apiUrl(runtime);
  const empty =
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n</urlset>\n';
  if (!baseUrl) return empty;
  try {
    const request = new Request(`${baseUrl}/v1/public/sitemaps/${kind}`, {
      headers: { accept: "application/xml" },
    });
    const response = runtime?.apiWorker
      ? await runtime.apiWorker.fetch(request)
      : await fetch(request);
    if (!response.ok) return empty;
    return await response.text();
  } catch {
    return empty;
  }
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
): Promise<SearchGroups> {
  if (apiUrl(runtime)) {
    const result = await fromApi<SearchGroups>(
      withCountry(`/v1/public/search?q=${encodeURIComponent(query)}`, country),
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
