/**
 * Rules and URL handling.
 *
 * `extractPage` itself is not covered here: it depends on HTMLRewriter, which
 * only exists inside workerd, and standing up the Workers vitest pool to
 * assert on parsing would test Cloudflare's parser more than our code. The
 * split in `extract.ts` is what makes that acceptable -- everything that
 * *decides* anything lives in `rules.ts` and takes a plain snapshot, so the
 * untested part is the mechanical bit that fills a struct.
 */

import { describe, expect, it } from "vitest";

import { normaliseInternalHref } from "./extract";
import { evaluateCrawl, evaluatePage } from "./rules";
import { extractTerms, scoreGaps } from "./keywords";
import { isAllowed, parseRobots } from "./robots";
import { type PageSnapshot, pageTypeFor } from "./types";

const ORIGIN = "https://www.truegritin.com";

function snapshot(overrides: Partial<PageSnapshot> = {}): PageSnapshot {
  const path = overrides.path ?? "/product/black-mustard-oil";
  return {
    path,
    statusCode: 200,
    pageType: pageTypeFor(path),
    title: "Black Mustard Oil, cold pressed | True Grit",
    h1: "Black Mustard Oil",
    headings: [],
    metaDescription:
      "Cold pressed black mustard oil from a single partner farm, bottled within days of pressing.",
    canonical: path,
    robots: "",
    h1Count: 1,
    wordCount: 400,
    imagesWithoutAlt: 0,
    schemaTypes: ["Product", "BreadcrumbList"],
    malformedSchemaBlocks: 0,
    schemaObjects: [
      {
        type: "Product",
        properties: {
          offers: { price: "450", priceCurrency: "INR", availability: "InStock" },
        },
      },
    ],
    hasAuthor: false,
    hasPublishedDate: false,
    internalLinks: ["/farms/vikas"],
    externalLinkCount: 0,
    ...overrides,
  };
}

function rules(findings: ReturnType<typeof evaluatePage>): string[] {
  return findings.map((finding) => finding.rule);
}

describe("pageTypeFor", () => {
  it("classifies detail routes from their prefix", () => {
    expect(pageTypeFor("/")).toBe("home");
    expect(pageTypeFor("/product/black-mustard-oil")).toBe("product");
    expect(pageTypeFor("/blog/why-cold-pressing")).toBe("article");
    expect(pageTypeFor("/recipes/dal")).toBe("recipe");
    expect(pageTypeFor("/returns")).toBe("policy");
  });

  it("does not read a bare listing prefix as a detail page", () => {
    expect(pageTypeFor("/product/")).toBe("other");
    expect(pageTypeFor("/shop")).toBe("other");
  });

  it("keeps /farms/partner out of the farm detail family", () => {
    // The route exists before `farms/:slug` for the same reason.
    expect(pageTypeFor("/farms/partner")).toBe("other");
    expect(pageTypeFor("/farms/vikas")).toBe("farm");
  });
});

describe("normaliseInternalHref", () => {
  it("keeps same-origin links as paths", () => {
    expect(normaliseInternalHref("/shop", ORIGIN)).toBe("/shop");
    expect(normaliseInternalHref(`${ORIGIN}/shop`, ORIGIN)).toBe("/shop");
  });

  it("drops other origins and non-http schemes", () => {
    expect(normaliseInternalHref("https://example.com/x", ORIGIN)).toBeNull();
    expect(normaliseInternalHref("mailto:hi@example.com", ORIGIN)).toBeNull();
    expect(normaliseInternalHref("#section", ORIGIN)).toBeNull();
  });

  it("normalises a trailing slash away so one page is not counted as two", () => {
    expect(normaliseInternalHref("/shop/", ORIGIN)).toBe("/shop");
    expect(normaliseInternalHref("/", ORIGIN)).toBe("/");
  });

  it("strips the fragment, because it is the same document", () => {
    expect(normaliseInternalHref("/returns#refunds", ORIGIN)).toBe("/returns");
  });
});

describe("indexing rules", () => {
  it("flags a sitemap URL that serves noindex as critical", () => {
    const findings = evaluatePage(snapshot({ robots: "noindex, follow" }));
    const noindex = findings.find((finding) => finding.rule === "noindex_in_sitemap");
    expect(noindex).toBeDefined();
    expect(noindex?.severity).toBe("critical");
  });

  it("flags a canonical pointing at another page", () => {
    const findings = evaluatePage(snapshot({ canonical: "/product/yellow-mustard-oil" }));
    expect(rules(findings)).toContain("canonical_points_elsewhere");
  });

  it("accepts a self-referencing absolute canonical", () => {
    const findings = evaluatePage(snapshot({ canonical: `${ORIGIN}/product/black-mustard-oil` }));
    expect(rules(findings)).not.toContain("canonical_points_elsewhere");
  });

  it("stops evaluating a page that errored, rather than piling on findings", () => {
    const findings = evaluatePage(snapshot({ statusCode: 404 }));
    expect(rules(findings)).toEqual(["sitemap_url_not_ok"]);
  });
});

describe("schema rules", () => {
  it("flags a product page with no Product markup", () => {
    const findings = evaluatePage(snapshot({ schemaTypes: [], schemaObjects: [] }));
    expect(rules(findings)).toContain("missing_product_schema");
  });

  it("treats a malformed block as worse than a missing one", () => {
    const findings = evaluatePage(snapshot({ malformedSchemaBlocks: 1 }));
    const malformed = findings.find((finding) => finding.rule === "malformed_schema");
    expect(malformed?.severity).toBe("high");
  });

  it("flags an offer missing price or availability", () => {
    const findings = evaluatePage(
      snapshot({
        schemaObjects: [{ type: "Product", properties: { offers: { price: "450" } } }],
      }),
    );
    const incomplete = findings.find((finding) => finding.rule === "product_offer_incomplete");
    expect(incomplete).toBeDefined();
    expect(incomplete?.evidence?.missing).toEqual(["priceCurrency", "availability"]);
  });

  it("accepts a complete product page", () => {
    expect(rules(evaluatePage(snapshot()))).not.toContain("product_offer_incomplete");
  });
});

describe("E-E-A-T rules", () => {
  it("flags an article with no author anywhere", () => {
    const findings = evaluatePage(
      snapshot({
        path: "/blog/why-cold-pressing",
        schemaTypes: ["Article", "BreadcrumbList"],
        schemaObjects: [
          { type: "Article", properties: { headline: "x", datePublished: "2026-01-01" } },
        ],
        hasAuthor: false,
        hasPublishedDate: true,
      }),
    );
    expect(rules(findings)).toContain("missing_author_signal");
  });

  it("does not ask a product page for an author", () => {
    expect(rules(evaluatePage(snapshot()))).not.toContain("missing_author_signal");
  });

  it("notes a product that does not link to its farm", () => {
    const findings = evaluatePage(snapshot({ internalLinks: ["/shop"] }));
    expect(rules(findings)).toContain("product_missing_farm_attribution");
  });
});

describe("cross-page rules", () => {
  it("reports a broken link once per target, not once per source", () => {
    const pages = [
      snapshot({ path: "/", internalLinks: ["/gone"] }),
      snapshot({ path: "/shop", internalLinks: ["/gone"] }),
      snapshot({ path: "/gone", statusCode: 404, internalLinks: [] }),
    ];
    const broken = evaluateCrawl(pages, new Set(["/", "/shop", "/gone"])).filter(
      (finding) => finding.rule === "broken_internal_link",
    );
    expect(broken).toHaveLength(1);
    expect(broken[0]?.evidence?.sources).toEqual(["/", "/shop"]);
  });

  it("flags a sitemap page nothing links to", () => {
    const pages = [
      snapshot({ path: "/", internalLinks: ["/shop"] }),
      snapshot({ path: "/shop", internalLinks: ["/"] }),
      snapshot({ path: "/product/orphan", internalLinks: ["/"] }),
    ];
    const orphans = evaluateCrawl(pages, new Set(["/", "/shop", "/product/orphan"])).filter(
      (finding) => finding.rule === "orphan_page",
    );
    expect(orphans.map((finding) => finding.path)).toEqual(["/product/orphan"]);
  });

  it("does not let a self-link rescue a page from being an orphan", () => {
    const pages = [
      snapshot({ path: "/", internalLinks: [] }),
      snapshot({ path: "/product/lonely", internalLinks: ["/product/lonely"] }),
    ];
    const orphans = evaluateCrawl(pages, new Set(["/", "/product/lonely"])).filter(
      (finding) => finding.rule === "orphan_page",
    );
    expect(orphans.map((finding) => finding.path)).toContain("/product/lonely");
  });

  it("reports duplicate titles against the later pages only", () => {
    const pages = [
      snapshot({ path: "/product/a", title: "Mustard Oil" }),
      snapshot({ path: "/product/b", title: "Mustard Oil" }),
      snapshot({ path: "/product/c", title: "Mustard Oil" }),
    ];
    const duplicates = evaluateCrawl(pages, new Set()).filter(
      (finding) => finding.rule === "duplicate_title",
    );
    expect(duplicates.map((finding) => finding.path)).toEqual(["/product/b", "/product/c"]);
  });
});

describe("robots.txt", () => {
  it("prefers a group naming us over the wildcard group", () => {
    const parsed = parseRobots(
      ["User-agent: *", "Disallow: /", "", "User-agent: TrueGritSeoAgent", "Disallow: /admin"].join(
        "\n",
      ),
    );
    expect(parsed.blocksEverything).toBe(false);
    expect(isAllowed(parsed, "/shop")).toBe(true);
    expect(isAllowed(parsed, "/admin/users")).toBe(false);
  });

  it("treats an empty Disallow as permission, per the standard", () => {
    const parsed = parseRobots("User-agent: *\nDisallow:");
    expect(isAllowed(parsed, "/anything")).toBe(true);
  });

  it("blocks everything under Disallow: /", () => {
    const parsed = parseRobots("User-agent: *\nDisallow: /");
    expect(parsed.blocksEverything).toBe(true);
    expect(isAllowed(parsed, "/shop")).toBe(false);
  });

  it("lets a more specific Allow override a broader Disallow", () => {
    const parsed = parseRobots("User-agent: *\nDisallow: /blog\nAllow: /blog/public");
    expect(isAllowed(parsed, "/blog/private")).toBe(false);
    expect(isAllowed(parsed, "/blog/public/post")).toBe(true);
  });

  it("ignores comments and malformed lines", () => {
    const parsed = parseRobots("# hello\nUser-agent: *\nnonsense\nDisallow: /x");
    expect(isAllowed(parsed, "/x/y")).toBe(false);
    expect(isAllowed(parsed, "/y")).toBe(true);
  });
});

describe("keyword gap scoring", () => {
  const competitorPages = [
    { title: "Cold pressed mustard oil", heading: "Cold pressed mustard oil", metaDescription: "" },
    { title: "Cold pressed sesame oil", heading: "Cold pressed sesame oil", metaDescription: "" },
    { title: "Cold pressed groundnut oil", heading: "Cold pressed oils", metaDescription: "" },
  ];

  it("does not count a term seen on only one page", () => {
    const terms = extractTerms([{ title: "single mention", heading: "", metaDescription: "" }]);
    expect(terms.size).toBe(0);
  });

  it("counts distinct pages, not repetitions within a page", () => {
    const terms = extractTerms([
      { title: "mustard mustard mustard", heading: "mustard", metaDescription: "mustard" },
      { title: "mustard", heading: "", metaDescription: "" },
    ]);
    expect(terms.get("mustard")?.pages).toBe(2);
  });

  it("does not build a phrase across a stopword", () => {
    const terms = extractTerms([
      { title: "oil for cooking", heading: "", metaDescription: "" },
      { title: "oil for cooking", heading: "", metaDescription: "" },
    ]);
    expect([...terms.keys()]).not.toContain("oil cooking");
  });

  it("surfaces a phrase competitors build around and we do not", () => {
    const gaps = scoreGaps(new Map(), [extractTerms(competitorPages)]);
    expect(gaps[0]?.term).toContain("cold pressed");
    expect(gaps[0]?.gapScore).toBeGreaterThan(0);
  });

  it("drops terms we already cover well", () => {
    const own = extractTerms([
      { title: "Cold pressed mustard oil", heading: "Cold pressed", metaDescription: "" },
      { title: "Cold pressed sesame oil", heading: "Cold pressed", metaDescription: "" },
      { title: "Cold pressed groundnut oil", heading: "Cold pressed", metaDescription: "" },
      { title: "Cold pressed coconut oil", heading: "Cold pressed", metaDescription: "" },
    ]);
    const gaps = scoreGaps(own, [extractTerms(competitorPages)]);
    expect(gaps.find((gap) => gap.term === "cold pressed")).toBeUndefined();
  });

  it("ranks a term two competitors share above one competitor's obsession", () => {
    const shared = [
      { title: "single origin turmeric", heading: "single origin", metaDescription: "" },
      { title: "single origin pepper", heading: "single origin", metaDescription: "" },
    ];
    const gaps = scoreGaps(new Map(), [extractTerms(shared), extractTerms(shared)]);
    const singleOrigin = gaps.find((gap) => gap.term === "single origin");
    expect(singleOrigin?.competitorCount).toBe(2);
  });
});
