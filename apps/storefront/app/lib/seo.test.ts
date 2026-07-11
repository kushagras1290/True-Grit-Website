import { describe, expect, it } from "vitest";

import { seoMeta } from "./seo";

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

  it("noindexes when no SEO document exists", () => {
    expect(seoMeta(null)).toContainEqual({ name: "robots", content: "noindex" });
  });
});
