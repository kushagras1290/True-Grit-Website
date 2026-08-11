import { describe, expect, it } from "vitest";

import {
  DEFAULT_SITE_DESCRIPTION,
  absoluteSiteUrl,
  breadcrumbJsonLd,
  productJsonLd,
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
