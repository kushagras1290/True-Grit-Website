import { describe, expect, it } from "vitest";

import {
  bootstrap,
  categories,
  products,
  productSlugsForCategory,
} from "@truegrit/contracts/fixtures";

import {
  loadAllProducts,
  loadCategories,
  loadCategoryPage,
  loadHighlightedProducts,
  loadProduct,
  loadProductPage,
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
    expect(product?.variants).toHaveLength(3);
    expect(product?.traceability.length).toBeGreaterThanOrEqual(4);
  });

  // Without PUBLIC_API_URL these fall back to fixtures; the deployed storefront
  // (which sets it) reads the same shapes from the live API.
  it("lists every fixture category and product when the API is off", async () => {
    expect(await loadCategories()).toEqual(categories);
    expect(await loadAllProducts()).toEqual(products);
  });

  it("ships the complete seeded market in demo mode", () => {
    expect(categories).toHaveLength(216);
    expect(products).toHaveLength(1500);
    expect(categories.filter((category) => category.level === 0).length).toBeGreaterThanOrEqual(46);
    expect(categories.map((category) => category.slug)).toEqual(
      expect.arrayContaining([
        "baby-kids",
        "bulk-refill-value",
        "chocolate-confectionery",
        "farm-fresh-proteins",
        "kitchen-dining-storage",
        "organic-gardening",
        "pasta-noodles-couscous",
        "pet-care",
        "regional-indian-pantry",
        "wellness-supplements",
      ]),
    );
    expect(products.map((product) => product.slug)).toEqual(
      expect.arrayContaining([
        "organic-a2-cow-milk",
        "organic-ashwagandha-capsules",
        "organic-frozen-green-peas",
        "organic-steel-lunch-box",
        "free-range-brown-eggs-farm-fresh-proteins",
        "brown-rice-penne-pasta-noodles-couscous",
        "70-percent-dark-chocolate-chocolate-confectionery",
        "weekly-vegetable-box-meal-boxes-subscriptions",
      ]),
    );
  });

  it("keeps every generated product purchasable and reachable from a category", () => {
    const assignedSlugs = new Set(
      categories.flatMap((category) => productSlugsForCategory(category.slug)),
    );
    expect(
      products.every(
        (product) =>
          product.leadVariantId !== null &&
          product.variants.length >= 2 &&
          product.variants.length <= 5 &&
          product.priceMinor > 0 &&
          assignedSlugs.has(product.slug),
      ),
    ).toBe(true);
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

  it("exposes tree position on every category so the shop can group them", () => {
    const departments = categories.filter((category) => category.level === 0);
    const subcategories = categories.filter((category) => category.level === 1);
    expect(departments.every((category) => category.parentId === null)).toBe(true);
    expect(subcategories.length).toBeGreaterThan(0);
    expect(
      subcategories.every((child) =>
        departments.some((department) => department.id === child.parentId),
      ),
    ).toBe(true);
  });

  it("resolves a department's sections for the drill-down", async () => {
    const page = await loadCategoryPage("fresh-fruits");
    expect(page?.subcategories.map((category) => category.slug)).toEqual(["stone-fruit"]);
  });
});

describe("shop grid filtering", () => {
  it("returns the full catalogue when no category is selected", async () => {
    const page = await loadProductPage(1);
    expect(page.total).toBe(products.length);
  });

  it("narrows the grid to the selected category", async () => {
    const page = await loadProductPage(1, undefined, undefined, "grains-and-millets");
    expect(page.items.map((product) => product.slug)).toEqual([
      "sprouted-ragi-flour",
      "himalayan-red-rajma",
    ]);
    expect(page.total).toBe(2);
  });

  it("narrows to a subcategory, not just a department", async () => {
    const page = await loadProductPage(1, undefined, undefined, "stone-fruit");
    expect(page.items.map((product) => product.slug)).toEqual(["organic-alphonso-mangoes"]);
  });

  // A stale bookmark must not silently widen back to the whole catalogue.
  it("returns an empty page for an unknown category", async () => {
    const page = await loadProductPage(1, undefined, undefined, "not-a-category");
    expect(page).toEqual({ items: [], total: 0 });
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
    const farms = await runSearch("bagi");
    expect(farms.groups.some((group) => group.group === "farms")).toBe(true);
    const articles = await runSearch("millets");
    expect(articles.groups.some((group) => group.group === "articles")).toBe(true);
  });
});
