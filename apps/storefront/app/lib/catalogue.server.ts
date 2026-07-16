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
  farms,
  getCategoryPage,
  homePage,
  products,
  recipes,
  categories,
} from "@truegrit/contracts/fixtures";

const API_URL = process.env.PUBLIC_API_URL || "";

async function fromApi<T>(path: string): Promise<T | null> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(5_000),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`API request failed: ${response.status}`);
  return (await response.json()) as T;
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
async function listFromApi<T>(path: string, fallback: T[]): Promise<T[]> {
  if (!API_URL) return fallback;
  const body = await fromApi<{ items: T[] }>(path);
  return body?.items ?? fallback;
}

export async function loadBootstrap(): Promise<PublicBootstrap> {
  if (API_URL) return (await fromApi<PublicBootstrap>("/v1/public/bootstrap")) ?? bootstrap;
  return bootstrap;
}

export async function loadHome(): Promise<PublicPage> {
  if (API_URL) return (await fromApi<PublicPage>("/v1/public/home")) ?? homePage;
  return homePage;
}

export async function loadCategoryPage(
  slug: string,
  country?: string,
): Promise<PublicCategoryPage | null> {
  if (API_URL) {
    return fromApi<PublicCategoryPage>(withCountry(`/v1/public/categories/${slug}`, country));
  }
  return getCategoryPage(slug);
}

export async function loadCategories(): Promise<CategorySummary[]> {
  return listFromApi<CategorySummary>("/v1/public/categories", categories);
}

export async function loadAllProducts(country?: string): Promise<ProductSummary[]> {
  return listFromApi<ProductSummary>(withCountry("/v1/public/products", country), products);
}

export async function loadProduct(slug: string, country?: string): Promise<ProductDetail | null> {
  if (API_URL) {
    return fromApi<ProductDetail>(withCountry(`/v1/public/products/${slug}`, country));
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
): Promise<ProductDetail[]> {
  if (slugs.length === 0) return [];
  const details = await Promise.all(slugs.map((slug) => loadProduct(slug, country)));
  return details.filter((product): product is ProductDetail => product !== null);
}

export async function loadProductsBySlugs(
  slugs: string[],
  country?: string,
): Promise<ProductSummary[]> {
  if (slugs.length === 0) return [];
  if (API_URL) {
    const query = slugs.map((slug) => encodeURIComponent(slug)).join(",");
    return listFromApi<ProductSummary>(
      withCountry(`/v1/public/products?slugs=${query}`, country),
      [],
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
export async function loadHighlightedProducts(country?: string): Promise<ProductSummary[]> {
  return listFromApi<ProductSummary>(
    withCountry("/v1/public/highlights", country),
    products.slice(0, 4),
  );
}

export async function loadFarms(): Promise<FarmDetail[]> {
  return farms;
}

export async function loadFarm(slug: string): Promise<FarmDetail | null> {
  return farms.find((farm) => farm.slug === slug) ?? null;
}

export async function loadRecipes(): Promise<RecipeDetail[]> {
  return recipes;
}

export async function loadRecipe(slug: string): Promise<RecipeDetail | null> {
  return recipes.find((recipe) => recipe.slug === slug) ?? null;
}

export async function loadArticles(): Promise<ArticleDetail[]> {
  return articles;
}

export async function loadArticle(slug: string): Promise<ArticleDetail | null> {
  return articles.find((article) => article.slug === slug) ?? null;
}

export interface SearchGroups {
  query: string;
  total: number;
  groups: Array<{
    group: string;
    items: Array<{ id: string; name: string; path: string; slug?: string }>;
  }>;
}

export async function runSearch(query: string, country?: string): Promise<SearchGroups> {
  if (API_URL) {
    const result = await fromApi<SearchGroups>(
      withCountry(`/v1/public/search?q=${encodeURIComponent(query)}`, country),
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
