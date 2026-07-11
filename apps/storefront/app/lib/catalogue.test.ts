import { describe, expect, it } from "vitest";

import { loadCategoryPage, loadProduct, runSearch } from "./catalogue.server";

describe("demo catalogue", () => {
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
});

describe("search", () => {
  it("matches synonyms like 'finger millet' -> ragi", async () => {
    const results = await runSearch("finger millet");
    const productGroup = results.groups.find((group) => group.group === "products");
    expect(productGroup?.items.some((item) => item.name.includes("Ragi"))).toBe(true);
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
