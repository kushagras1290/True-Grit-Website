/**
 * Proposal generation.
 *
 * These are the tests that matter most in this app. A proposal becomes an
 * UPDATE against the live catalogue as soon as somebody clicks Apply, so the
 * properties asserted here are safety properties, not quality ones: never
 * invent a claim, never propose a column the table does not have, never
 * silently overwrite something that is already fine.
 */

import { describe, expect, it } from "vitest";

import type { KeywordGap } from "./keywords";
import {
  SUPPORTED_FIELDS,
  type SeoEntity,
  headingKey,
  matchTerms,
  proposalsFor,
} from "./proposals";

function gap(term: string, score = 20): KeywordGap {
  const wordCount = term.split(" ").length;
  return {
    term,
    termWords: wordCount,
    ownPages: 0,
    ownTitleHits: 0,
    ownHeadingHits: 0,
    competitorPages: 5,
    competitorTitleHits: 3,
    competitorHeadingHits: 2,
    competitorCount: 2,
    gapScore: score,
  };
}

function product(overrides: Partial<SeoEntity> = {}): SeoEntity {
  return {
    entityType: "product",
    entityId: "prd_1",
    label: "Black Mustard Oil",
    path: "/product/black-mustard-oil",
    name: "Black Mustard Oil",
    description:
      "Cold pressed black mustard oil, bottled within days of pressing and never refined.",
    context: ["Vikas Farms"],
    seoTitle: "",
    seoDescription: "",
    seoKeywords: "",
    indexingPolicy: "index",
    supportedFields: SUPPORTED_FIELDS.product,
    ...overrides,
  };
}

function fields(proposals: ReturnType<typeof proposalsFor>): string[] {
  return proposals.map((proposal) => proposal.field);
}

describe("matchTerms", () => {
  it("only matches terms the entity's own words already contain", () => {
    const matched = matchTerms(product(), [gap("cold pressed"), gap("single origin")]);
    expect(matched.map((item) => item.term)).toEqual(["cold pressed"]);
  });

  it("rejects a term whose words are not all present", () => {
    // "stone ground" is a real competitor phrase, and claiming it for an oil
    // would be a lie the agent must not tell.
    const matched = matchTerms(product(), [gap("stone ground")]);
    expect(matched).toEqual([]);
  });

  it("returns nothing when the entity has no text to match against", () => {
    const matched = matchTerms(product({ name: "", description: "", context: [] }), [
      gap("cold pressed"),
    ]);
    expect(matched).toEqual([]);
  });
});

describe("title proposals", () => {
  it("proposes a title when none is set, working a matched phrase in", () => {
    const [proposal] = proposalsFor(product(), [gap("cold pressed")], new Set());
    expect(proposal?.field).toBe("seo_title");
    expect(proposal?.proposedValue).toContain("Black Mustard Oil");
    expect(proposal?.proposedValue).toContain("cold pressed");
  });

  it("keeps the proposed title inside the snippet limit", () => {
    const proposals = proposalsFor(
      product({
        name: "Traditionally Cold Pressed Single Origin Black Mustard Oil From The Hills",
      }),
      [gap("cold pressed")],
      new Set(),
    );
    const title = proposals.find((proposal) => proposal.field === "seo_title");
    expect(title!.proposedValue.length).toBeLessThanOrEqual(60);
  });

  it("leaves a good existing title alone", () => {
    const proposals = proposalsFor(
      product({ seoTitle: "Black Mustard Oil, cold pressed | True Grit" }),
      [gap("cold pressed")],
      new Set(),
    );
    expect(fields(proposals)).not.toContain("seo_title");
  });

  it("replaces a title the crawl flagged as too long", () => {
    const proposals = proposalsFor(
      product({ seoTitle: "x".repeat(120) }),
      [gap("cold pressed")],
      new Set(["title_too_long"]),
    );
    expect(fields(proposals)).toContain("seo_title");
  });

  it("proposes nothing at all for an entity with no name", () => {
    const proposals = proposalsFor(
      product({ name: "", description: "", context: [] }),
      [gap("cold pressed")],
      new Set(),
    );
    expect(fields(proposals)).not.toContain("seo_title");
  });
});

describe("description proposals", () => {
  it("builds a description only from the entity's own prose", () => {
    const proposals = proposalsFor(product(), [], new Set());
    const description = proposals.find((proposal) => proposal.field === "seo_description");
    expect(description?.proposedValue).toContain("Cold pressed black mustard oil");
    expect(description!.proposedValue.length).toBeLessThanOrEqual(155);
  });

  it("refuses to invent one when the entity has no description", () => {
    const proposals = proposalsFor(product({ description: "" }), [], new Set());
    expect(fields(proposals)).not.toContain("seo_description");
  });

  it("refuses when the source prose is too short to be worth trimming", () => {
    const proposals = proposalsFor(product({ description: "Mustard oil." }), [], new Set());
    expect(fields(proposals)).not.toContain("seo_description");
  });

  it("never cuts mid-word", () => {
    const proposals = proposalsFor(
      product({ description: `${"words ".repeat(60)}end` }),
      [],
      new Set(),
    );
    const value = proposals.find((proposal) => proposal.field === "seo_description")!.proposedValue;
    expect(value.endsWith("word")).toBe(false);
  });
});

describe("schema-shape safety", () => {
  it("never proposes seo_keywords for a product, which has no such column", () => {
    const proposals = proposalsFor(product(), [gap("cold pressed")], new Set());
    expect(fields(proposals)).not.toContain("seo_keywords");
  });

  it("does propose seo_keywords for an article, which does have the column", () => {
    const article: SeoEntity = {
      ...product(),
      entityType: "article",
      entityId: "art_1",
      path: "/blog/cold-pressing",
      name: "Why cold pressed oil keeps its flavour",
      description: "How cold pressed oil differs from refined oil, and why it matters in cooking.",
      supportedFields: SUPPORTED_FIELDS.article,
    };
    const proposals = proposalsFor(article, [gap("cold pressed")], new Set());
    expect(fields(proposals)).toContain("seo_keywords");
  });

  it("only ever adds keywords, keeping the existing ones", () => {
    const article: SeoEntity = {
      ...product(),
      entityType: "article",
      name: "Cold pressed oil explained",
      description: "How cold pressed oil differs from refined oil, and why it matters in cooking.",
      seoKeywords: "mustard oil",
      supportedFields: SUPPORTED_FIELDS.article,
    };
    const keywords = proposalsFor(article, [gap("cold pressed")], new Set()).find(
      (proposal) => proposal.field === "seo_keywords",
    );
    expect(keywords?.proposedValue).toContain("mustard oil");
    expect(keywords?.proposedValue).toContain("cold pressed");
  });
});

describe("indexing proposals", () => {
  it("proposes index only when the crawl actually saw the contradiction", () => {
    const noindexed = product({ indexingPolicy: "noindex" });
    expect(fields(proposalsFor(noindexed, [], new Set()))).not.toContain("indexing_policy");
    expect(fields(proposalsFor(noindexed, [], new Set(["noindex_in_sitemap"])))).toContain(
      "indexing_policy",
    );
  });

  it("scores the indexing change below the copy changes, because it needs a look", () => {
    const proposal = proposalsFor(
      product({ indexingPolicy: "noindex" }),
      [],
      new Set(["noindex_in_sitemap"]),
    ).find((item) => item.field === "indexing_policy");
    expect(proposal!.confidence).toBeLessThan(0.8);
  });
});

describe("headingKey", () => {
  it("collapses wording variants of the same section", () => {
    expect(headingKey("FAQs")).toBe("faq");
    expect(headingKey("Frequently Asked Questions")).toBe("faq");
    expect(headingKey("How to store")).toBe("storage");
    expect(headingKey("Shelf life")).toBe("storage");
  });

  it("leaves an unrecognised heading as its normalised text", () => {
    expect(headingKey("Our  Pressing   Method!")).toBe("our pressing method");
  });
});
