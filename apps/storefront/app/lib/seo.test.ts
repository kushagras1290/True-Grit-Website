import { describe, expect, it } from "vitest";

import {
  DEFAULT_SITE_DESCRIPTION,
  absoluteSiteUrl,
  breadcrumbJsonLd,
  productJsonLd,
  recipeJsonLd,
  recipeStepAnchor,
  seoMeta,
} from "./seo";

describe("seoMeta", () => {
  it("appends the site name once", () => {
    const meta = seoMeta({
      title: "Fresh Fruits",
      description: "Seasonal organic fruit.",
      canonicalPath: "/category/fresh-fruits",
      indexing: "index",
    });
    const title = meta.find((entry) => "title" in entry) as { title: string };
    expect(title.title).toBe("Fresh Fruits · True Grit");

    const already = seoMeta({
      title: "True Grit — traceable organic food",
      description: "x",
      canonicalPath: "/",
      indexing: "index",
    });
    const alreadyTitle = already.find((entry) => "title" in entry) as { title: string };
    expect(alreadyTitle.title).toBe("True Grit — traceable organic food");
  });

  it("maps indexing policy to robots", () => {
    const indexed = seoMeta({
      title: "t",
      description: "d",
      canonicalPath: "/",
      indexing: "index",
    });
    expect(indexed).toContainEqual({ name: "robots", content: "index, follow" });

    const hidden = seoMeta({
      title: "t",
      description: "d",
      canonicalPath: "/",
      indexing: "noindex",
    });
    expect(hidden).toContainEqual({ name: "robots", content: "noindex, nofollow" });
  });

  it("always emits an absolute, non-empty canonical and description", () => {
    const meta = seoMeta({
      title: "Home",
      description: "",
      canonicalPath: "",
      indexing: "index",
    });
    expect(meta).toContainEqual({
      tagName: "link",
      rel: "canonical",
      href: "https://www.truegritin.com/",
    });
    expect(meta).toContainEqual({ name: "description", content: DEFAULT_SITE_DESCRIPTION });
    expect(absoluteSiteUrl("/product/kathiya-wheat-flour")).toBe(
      "https://www.truegritin.com/product/kathiya-wheat-flour",
    );
  });

  it("builds Product and BreadcrumbList JSON-LD with absolute URLs", () => {
    const product = productJsonLd({
      name: "Kathiya Wheat Flour",
      description: "Traditional whole-wheat flour.",
      canonicalPath: "/product/kathiya-wheat-flour",
      priceMinor: 5500,
      currencyCode: "INR",
      availability: "in_stock",
    })["script:ld+json"];
    expect(product).toMatchObject({
      "@type": "Product",
      url: "https://www.truegritin.com/product/kathiya-wheat-flour",
      offers: { price: "55.00", priceCurrency: "INR" },
    });

    const breadcrumbs = breadcrumbJsonLd([
      { name: "Home", path: "/" },
      { name: "Product", path: "/product/kathiya-wheat-flour" },
    ])["script:ld+json"];
    expect(breadcrumbs).toMatchObject({
      "@type": "BreadcrumbList",
      itemListElement: [
        { position: 1, item: "https://www.truegritin.com/" },
        { position: 2, item: "https://www.truegritin.com/product/kathiya-wheat-flour" },
      ],
    });
  });

  it("noindexes when no SEO document exists", () => {
    expect(seoMeta(null)).toContainEqual({ name: "robots", content: "noindex" });
  });
});

describe("recipeJsonLd", () => {
  const base = {
    title: "Sattu Paratha",
    excerpt: "Roasted gram flour stuffed flatbread.",
    prepMinutes: 20,
    cookMinutes: 15,
    servings: 4,
    ingredients: [{ label: "black gram sattu", quantityText: "200 g" }],
    steps: [
      "Mix the sattu with onion and spices. Rub it between your palms until it holds together loosely.",
      "Roll and cook on a hot tawa.",
    ],
    canonicalPath: "/recipes/sattu-paratha",
  };

  it("reports a total time Google does not have to derive", () => {
    const recipe = recipeJsonLd(base)["script:ld+json"];
    expect(recipe).toMatchObject({
      prepTime: "PT20M",
      cookTime: "PT15M",
      totalTime: "PT35M",
      author: { "@type": "Organization", name: "True Grit" },
    });
  });

  it("states a cuisine only when the recipe carries one", () => {
    expect(recipeJsonLd({ ...base, cuisine: "Indian" })["script:ld+json"]).toMatchObject({
      recipeCuisine: "Indian",
    });
    expect(recipeJsonLd({ ...base, cuisine: "Italian" })["script:ld+json"]).toMatchObject({
      recipeCuisine: "Italian",
    });
    // No site-wide fallback: an unset cuisine must not become "Indian" on a
    // recipe written for another market.
    expect(recipeJsonLd(base)["script:ld+json"]).not.toHaveProperty("recipeCuisine");
    expect(recipeJsonLd({ ...base, cuisine: null })["script:ld+json"]).not.toHaveProperty(
      "recipeCuisine",
    );
    expect(recipeJsonLd({ ...base, cuisine: "  " })["script:ld+json"]).not.toHaveProperty(
      "recipeCuisine",
    );
  });

  it("gives every step a resolvable anchor and names only the ones worth naming", () => {
    const recipe = recipeJsonLd(base)["script:ld+json"] as {
      recipeInstructions: Array<{ name?: string; text: string; url: string }>;
    };
    expect(recipe.recipeInstructions[0]).toMatchObject({
      name: "Mix the sattu with onion and spices.",
      url: "https://www.truegritin.com/recipes/sattu-paratha#step-1",
    });
    // Single-sentence step: a `name` here would merely restate `text`.
    expect(recipe.recipeInstructions[1]).not.toHaveProperty("name");
    expect(recipe.recipeInstructions[1]).toMatchObject({
      url: "https://www.truegritin.com/recipes/sattu-paratha#step-2",
    });
    expect(recipe.recipeInstructions.map((_, index) => recipeStepAnchor(index))).toEqual([
      "step-1",
      "step-2",
    ]);
  });

  it("prefers editor keywords over dietary tags, and omits the field when neither exists", () => {
    expect(
      recipeJsonLd({ ...base, keywords: "sattu, paratha", dietaryTags: ["vegetarian"] })[
        "script:ld+json"
      ],
    ).toMatchObject({ keywords: "sattu, paratha" });

    expect(
      recipeJsonLd({ ...base, keywords: "   ", dietaryTags: ["vegetarian", "high protein"] })[
        "script:ld+json"
      ],
    ).toMatchObject({ keywords: "vegetarian, high protein" });

    expect(recipeJsonLd(base)["script:ld+json"]).not.toHaveProperty("keywords");
  });

  it("never invents ratings, nutrition or video it has no data for", () => {
    const recipe = recipeJsonLd(base)["script:ld+json"];
    expect(recipe).not.toHaveProperty("aggregateRating");
    expect(recipe).not.toHaveProperty("nutrition");
    expect(recipe).not.toHaveProperty("video");
  });
});
