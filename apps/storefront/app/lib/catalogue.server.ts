/**
 * Server-side data access for route loaders.
 *
 * With `PUBLIC_API_URL` set, loaders call the FastAPI public endpoints. In
 * demo-data mode they resolve the deterministic fixture catalogue so the full
 * storefront renders (and is testable) before Cloudflare resources exist.
 */

import type {
  ArticleDetail,
  FarmDetail,
  ProductDetail,
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

export async function loadBootstrap(): Promise<PublicBootstrap> {
  if (API_URL) return (await fromApi<PublicBootstrap>("/v1/public/bootstrap")) ?? bootstrap;
  return bootstrap;
}

export async function loadHome(): Promise<PublicPage> {
  if (API_URL) return (await fromApi<PublicPage>("/v1/public/home")) ?? homePage;
  return homePage;
}

export async function loadCategoryPage(slug: string): Promise<PublicCategoryPage | null> {
  if (API_URL) return fromApi<PublicCategoryPage>(`/v1/public/categories/${slug}`);
  return getCategoryPage(slug);
}

export async function loadCategories() {
  return categories;
}

export async function loadProduct(slug: string): Promise<ProductDetail | null> {
  if (API_URL) return fromApi<ProductDetail>(`/v1/public/products/${slug}`);
  return products.find((product) => product.slug === slug) ?? null;
}

export function loadProductsBySlugs(slugs: string[]): ProductDetail[] {
  const bySlug = new Map(products.map((product) => [product.slug, product]));
  return slugs.flatMap((slug) => bySlug.get(slug) ?? []);
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
  groups: Array<{ group: string; items: Array<{ id: string; name: string; path: string }> }>;
}

export async function runSearch(query: string): Promise<SearchGroups> {
  if (API_URL) {
    const result = await fromApi<SearchGroups>(`/v1/public/search?q=${encodeURIComponent(query)}`);
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
    .map((product) => ({ id: product.id, name: product.name, path: `/product/${product.slug}` }));
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
