import { describe, expect, it } from "vitest";

import { bootstrap, categories, products } from "@truegrit/contracts/fixtures";

import {
  loadAllProducts,
  loadCategories,
  loadCategoryPage,
  loadHighlightedProducts,
  loadProduct,
  loadProductsBySlugs,
  runSearch,
} from "./catalogue.server";

describe("demo catalogue", () => {
  it("points every footer support link at a built static route", () => {
    expect(bootstrap.navigation.find((item) => item.label === "Seasonal")?.path).toBe("/seasonal");
    expect(bootstrap.footerNavigation.map((item) => item.path)).toEqual([
      "/about",
      "/delivery",
      "/returns",
      "/contact",
      "/privacy",
      "/terms",
      "/help",
    ]);
  });

  it("resolves a category page with products and SEO", async () => {
    const page = await loadCategoryPage("fresh-fruits");
    expect(page?.hero.title).toBe("Fruit, at its honest best");
    expect(page?.products.map((product) => product.slug)).toEqual(["organic-alphonso-mangoes"]);
    expect(page?.seo.canonicalPath).toBe("/category/fresh-fruits");
  });

  it("returns null for unknown categories (404 path)", async () => {
    expect(await loadCategoryPage("not-real")).toBeNull();
  });

  it("resolves product detail with variants and traceability", async () => {
    const product = await loadProduct("sprouted-ragi-flour");
    expect(product?.variants).toHaveLength(2);
    expect(product?.traceability.length).toBeGreaterThanOrEqual(4);
  });

  // Without PUBLIC_API_URL these fall back to fixtures; the deployed storefront
  // (which sets it) reads the same shapes from the live API.
  it("lists every fixture category and product when the API is off", async () => {
    expect(await loadCategories()).toEqual(categories);
    expect(await loadAllProducts()).toEqual(products);
  });

  it("loads products by slug in the requested order", async () => {
    const result = await loadProductsBySlugs(["sprouted-ragi-flour", "organic-alphonso-mangoes"]);
    expect(result.map((product) => product.slug)).toEqual([
      "sprouted-ragi-flour",
      "organic-alphonso-mangoes",
    ]);
  });

  it("returns an empty list for no slugs without hitting the catalogue", async () => {
    expect(await loadProductsBySlugs([])).toEqual([]);
  });

  it("falls back to fixture products for the highlights box in demo mode", async () => {
    const highlights = await loadHighlightedProducts("IN");
    expect(highlights.length).toBeGreaterThan(0);
    expect(highlights[0]?.slug).toBe(products[0]?.slug);
  });
});

describe("search", () => {
  it("matches synonyms like 'finger millet' -> ragi", async () => {
    const results = await runSearch("finger millet");
    const productGroup = results.groups.find((group) => group.group === "products");
    expect(productGroup?.items.some((item) => item.name.includes("Ragi"))).toBe(true);
  });

  it("returns product slugs so the search page can render price cards", async () => {
    const results = await runSearch("rajma");
    const productGroup = results.groups.find((group) => group.group === "products");
    expect(productGroup?.items[0]?.slug).toBe("himalayan-red-rajma");
  });

  it("returns a safe empty state for gibberish", async () => {
    const results = await runSearch("zzzzz");
    expect(results.total).toBe(0);
    expect(results.groups).toEqual([]);
  });

  it("groups farm and article results", async () => {
    const farms = await runSearch("devika");
    expect(farms.groups.some((group) => group.group === "farms")).toBe(true);
    const articles = await runSearch("millets");
    expect(articles.groups.some((group) => group.group === "articles")).toBe(true);
  });
});
