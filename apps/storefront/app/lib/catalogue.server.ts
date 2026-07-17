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
  products,
  recipes,
} from "@truegrit/contracts/fixtures";

export interface CatalogueRuntime {
  apiUrl?: string;
}

export function catalogueRuntime(context: unknown): CatalogueRuntime {
  return {
    apiUrl: (context as { cloudflare?: { env?: { PUBLIC_API_URL?: string } } } | undefined)
      ?.cloudflare?.env?.PUBLIC_API_URL,
  };
}

function apiUrl(runtime?: CatalogueRuntime): string {
  return (runtime?.apiUrl || process.env.PUBLIC_API_URL || "").trim().replace(/\/+$/, "");
}

async function fromApi<T>(path: string, runtime?: CatalogueRuntime): Promise<T | null> {
  const baseUrl = apiUrl(runtime);
  if (!baseUrl) return null;
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      headers: { accept: "application/json" },
    });
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

// List endpoints wrap their rows in `{ items }`. Unwrap, and fall back to the
// supplied fixture when the API is not configured or returns nothing — a
// storefront should degrade to demo data, never crash a page, if a list is
// briefly unavailable.
async function listFromApi<T>(
  path: string,
  fallback: T[],
  runtime?: CatalogueRuntime,
): Promise<T[]> {
  if (!apiUrl(runtime)) return fallback;
  const body = await fromApi<{ items: T[] }>(path, runtime);
  return body?.items ?? fallback;
}

export async function loadBootstrap(runtime?: CatalogueRuntime): Promise<PublicBootstrap> {
  if (apiUrl(runtime))
    return (await fromApi<PublicBootstrap>("/v1/public/bootstrap", runtime)) ?? bootstrap;
  return bootstrap;
}

export async function loadHome(runtime?: CatalogueRuntime): Promise<PublicPage> {
  if (apiUrl(runtime)) return (await fromApi<PublicPage>("/v1/public/home", runtime)) ?? homePage;
  return homePage;
}

export async function loadPage(
  slug: string,
  runtime?: CatalogueRuntime,
): Promise<PublicPage | null> {
  if (!apiUrl(runtime)) return slug === "home" ? homePage : null;
  return fromApi<PublicPage>(`/v1/public/pages/${encodeURIComponent(slug)}`, runtime);
}

export async function loadCategoryPage(
  slug: string,
  country?: string,
  runtime?: CatalogueRuntime,
): Promise<PublicCategoryPage | null> {
  if (apiUrl(runtime)) {
    return (
      (await fromApi<PublicCategoryPage>(
        withCountry(`/v1/public/categories/${slug}`, country),
        runtime,
      )) ?? getCategoryPage(slug)
    );
  }
  return getCategoryPage(slug);
}

export async function loadCategories(runtime?: CatalogueRuntime): Promise<CategorySummary[]> {
  return listFromApi<CategorySummary>("/v1/public/categories", categories, runtime);
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

export async function loadProduct(
  slug: string,
  country?: string,
  runtime?: CatalogueRuntime,
): Promise<ProductDetail | null> {
  if (apiUrl(runtime)) {
    return (
      (await fromApi<ProductDetail>(
        withCountry(`/v1/public/products/${slug}`, country),
        runtime,
      )) ??
      products.find((product) => product.slug === slug) ??
      null
    );
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
    return (
      (await fromApi<FarmDetail>(`/v1/public/farms/${encodeURIComponent(slug)}`, runtime)) ??
      farms.find((farm) => farm.slug === slug) ??
      null
    );
  }
  return farms.find((farm) => farm.slug === slug) ?? null;
}

export async function loadRecipes(runtime?: CatalogueRuntime): Promise<RecipeDetail[]> {
  return listFromApi<RecipeDetail>("/v1/public/recipes", recipes, runtime);
}

export async function loadRecipe(
  slug: string,
  runtime?: CatalogueRuntime,
): Promise<RecipeDetail | null> {
  if (apiUrl(runtime)) {
    return (
      (await fromApi<RecipeDetail>(`/v1/public/recipes/${encodeURIComponent(slug)}`, runtime)) ??
      recipes.find((recipe) => recipe.slug === slug) ??
      null
    );
  }
  return recipes.find((recipe) => recipe.slug === slug) ?? null;
}

export async function loadArticles(runtime?: CatalogueRuntime): Promise<ArticleDetail[]> {
  return listFromApi<ArticleDetail>("/v1/public/articles", articles, runtime);
}

export async function loadArticle(
  slug: string,
  runtime?: CatalogueRuntime,
): Promise<ArticleDetail | null> {
  if (apiUrl(runtime)) {
    return (
      (await fromApi<ArticleDetail>(`/v1/public/articles/${encodeURIComponent(slug)}`, runtime)) ??
      articles.find((article) => article.slug === slug) ??
      null
    );
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
    if (result) return result;
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
    .map((article) => ({ id: article.id, name: article.title, path: `/journal/${article.slug}` }));
  if (articleItems.length) groups.push({ group: "articles", items: articleItems });

  return {
    query,
    total: groups.reduce((sum, group) => sum + group.items.length, 0),
    groups,
  };
}
