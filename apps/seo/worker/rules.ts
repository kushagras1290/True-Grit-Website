/**
 * Snapshots -> findings. Pure functions, no network, no D1.
 *
 * Two kinds of rule, and the split is not cosmetic:
 *
 * * **Per-page rules** answer from one snapshot. Most schema and content
 *   checks are these.
 * * **Cross-page rules** need the whole crawl: a link is only broken once you
 *   know what every URL returned, and a page is only orphaned once you know
 *   nothing links to it. These run in `evaluateCrawl` after every page is in.
 *
 * Severity is assigned by consequence, not by how easy the fix is. The
 * `indexing` category sits at the top because those are the findings that stop
 * a page being in the index at all, which is the concrete problem this agent
 * was built for: a URL published in the sitemap while serving `noindex`, or
 * canonicalising somewhere else, is invisible no matter how good its schema is.
 * A missing meta description is a worse snippet, not a missing page, and is
 * scored accordingly.
 *
 * Every finding carries a `fixHint` naming what to change. A finding an
 * operator cannot act on is noise, and this is the field the PR generator
 * reads.
 */

import type { Finding, PageSnapshot, PageType } from "./types";

// Google truncates around these; they are guidance for the snippet, not hard
// limits, so both are `low` severity.
const TITLE_MAX = 60;
const TITLE_MIN = 15;
const META_DESCRIPTION_MAX = 160;
const META_DESCRIPTION_MIN = 50;
// Below this a detail page has little for a crawler to rank and reads as
// scaffolding rather than content.
const THIN_CONTENT_WORDS = 150;

/** Which JSON-LD `@type` each page family is expected to carry, and how badly
 *  it matters when it is missing. Detail pages are where rich results come
 *  from, so those are `high`. */
const REQUIRED_SCHEMA: Partial<Record<PageType, { type: string; severity: "high" | "medium" }>> = {
  product: { type: "Product", severity: "high" },
  article: { type: "Article", severity: "high" },
  recipe: { type: "Recipe", severity: "high" },
  home: { type: "Organization", severity: "medium" },
};

/** Page families that are a single item and should therefore carry a
 *  breadcrumb trail. Listing pages legitimately do not. */
const BREADCRUMB_TYPES: PageType[] = ["product", "article", "recipe", "farm", "bundle", "category"];

const DETAIL_TYPES: PageType[] = ["product", "article", "recipe", "farm", "bundle"];

function has(snapshot: PageSnapshot, type: string): boolean {
  return snapshot.schemaTypes.includes(type);
}

function schemaOf(snapshot: PageSnapshot, type: string) {
  return snapshot.schemaObjects.find((object) => object.type === type);
}

function isNoindex(snapshot: PageSnapshot): boolean {
  return snapshot.robots.includes("noindex");
}

/** Findings answerable from a single page. */
export function evaluatePage(snapshot: PageSnapshot): Finding[] {
  const findings: Finding[] = [];
  const { path, pageType } = snapshot;
  const add = (finding: Omit<Finding, "path" | "pageType">) =>
    findings.push({ ...finding, path, pageType });

  // --- Indexing. The category that decides whether the page exists at all.
  if (snapshot.statusCode >= 400) {
    add({
      rule: "sitemap_url_not_ok",
      category: "indexing",
      severity: "critical",
      summary: `Sitemap URL returns ${snapshot.statusCode}`,
      detail:
        `This URL is published in the sitemap but responded ${snapshot.statusCode}. Search` +
        " engines treat a sitemap as a list of pages you are asking to be indexed, so a dead" +
        " entry wastes crawl budget and undermines trust in the rest of the file.",
      fixHint:
        "Either restore the page or remove it from the sitemap generator so the file only" +
        " lists URLs that resolve.",
      evidence: { statusCode: snapshot.statusCode },
    });
    // Nothing else can be judged from an error page.
    return findings;
  }

  if (isNoindex(snapshot)) {
    add({
      rule: "noindex_in_sitemap",
      category: "indexing",
      severity: "critical",
      summary: "Page is in the sitemap but serves noindex",
      detail:
        "The sitemap asks search engines to index this URL while the page itself tells them" +
        " not to. The robots directive wins, so the page will never appear in results, and" +
        " the contradiction is the single most common cause of a page silently staying out" +
        " of the index.",
      fixHint:
        "Decide which is right. If the page should rank, clear its indexing policy" +
        " (Admin > the entity's SEO fields, or route_seo_overrides). If it should not," +
        " exclude it from the sitemap generator.",
      evidence: { robots: snapshot.robots },
    });
  }

  if (!snapshot.canonical) {
    add({
      rule: "canonical_missing",
      category: "indexing",
      severity: "medium",
      summary: "No canonical URL",
      detail:
        "Without a canonical, any URL variant that reaches this page (tracking parameters," +
        " a trailing slash, an alternate casing) can be treated as a separate document and" +
        " split its ranking signals.",
      fixHint: 'Emit a self-referencing <link rel="canonical"> from the route\'s meta export.',
    });
  } else {
    let canonicalPath = snapshot.canonical;
    try {
      canonicalPath = new URL(snapshot.canonical, "https://example.invalid").pathname;
    } catch {
      /* Keep the raw value; the comparison below then reports it as-is. */
    }
    const normalised =
      canonicalPath.length > 1 && canonicalPath.endsWith("/")
        ? canonicalPath.slice(0, -1)
        : canonicalPath;
    if (normalised !== path) {
      add({
        rule: "canonical_points_elsewhere",
        category: "indexing",
        severity: "high",
        summary: "Canonical points at a different page",
        detail:
          `This page is in the sitemap but canonicalises to ${normalised}. That tells search` +
          " engines to index the other URL instead, so this one will not rank on its own.",
        fixHint:
          "If this page should rank, make the canonical self-referencing. If it is genuinely a" +
          " duplicate, drop it from the sitemap.",
        evidence: { canonical: snapshot.canonical, expected: path },
      });
    }
  }

  // --- Schema markup.
  const required = REQUIRED_SCHEMA[pageType];
  if (required && !has(snapshot, required.type)) {
    add({
      rule: `missing_${required.type.toLowerCase()}_schema`,
      category: "schema",
      severity: required.severity,
      summary: `No ${required.type} structured data`,
      detail:
        `A ${pageType} page without ${required.type} JSON-LD cannot produce a rich result.` +
        " The information is already on the page; it is the machine-readable copy that is" +
        " missing.",
      fixHint: `Render ${required.type} JSON-LD from apps/storefront/app/lib/seo.ts on this route.`,
      evidence: { found: snapshot.schemaTypes },
    });
  }

  if (BREADCRUMB_TYPES.includes(pageType) && !has(snapshot, "BreadcrumbList")) {
    add({
      rule: "missing_breadcrumb_schema",
      category: "schema",
      severity: "low",
      summary: "No BreadcrumbList structured data",
      detail:
        "Breadcrumb markup replaces the bare URL in the search result with the page's place in" +
        " the site, which is both clearer to a reader and a hierarchy signal to the crawler.",
      fixHint: "Call breadcrumbJsonLd() in this route's meta export.",
    });
  }

  if (snapshot.malformedSchemaBlocks > 0) {
    add({
      rule: "malformed_schema",
      category: "schema",
      severity: "high",
      summary: `${snapshot.malformedSchemaBlocks} JSON-LD block(s) failed to parse`,
      detail:
        "A structured data block that is not valid JSON is discarded silently. The page looks" +
        " marked up in the source and carries no markup at all as far as a crawler is" +
        " concerned, which is why this is worth more attention than a missing block.",
      fixHint:
        "Check for unescaped quotes or a trailing comma in the values interpolated into the" +
        " JSON-LD for this route.",
      evidence: { blocks: snapshot.malformedSchemaBlocks },
    });
  }

  const product = schemaOf(snapshot, "Product");
  if (product) {
    const offers = product.properties.offers as Record<string, unknown> | undefined;
    const missing = ["price", "priceCurrency", "availability"].filter(
      (key) => !offers || offers[key] === undefined || offers[key] === null || offers[key] === "",
    );
    if (!offers || missing.length > 0) {
      add({
        rule: "product_offer_incomplete",
        category: "schema",
        severity: "medium",
        summary: "Product schema has no complete offer",
        detail:
          "Price, currency and availability are what turn a Product result into one showing" +
          " the price. Without all three the markup is valid and produces nothing extra.",
        fixHint: `Add ${missing.join(", ") || "an offers object"} to the Product JSON-LD.`,
        evidence: { missing },
      });
    }
  }

  const recipe = schemaOf(snapshot, "Recipe");
  if (recipe) {
    const missing = ["image", "recipeIngredient", "recipeInstructions"].filter(
      (key) => !recipe.properties[key],
    );
    if (missing.length > 0) {
      add({
        rule: "recipe_schema_incomplete",
        category: "schema",
        severity: "medium",
        summary: "Recipe schema is missing required properties",
        detail:
          "Recipe rich results require an image, an ingredient list and instructions. Missing" +
          " any of them disqualifies the page from the recipe carousel entirely.",
        fixHint: `Populate ${missing.join(", ")} in the Recipe JSON-LD.`,
        evidence: { missing },
      });
    }
  }

  const article = schemaOf(snapshot, "Article");
  if (article) {
    const missing = ["author", "datePublished", "headline"].filter(
      (key) => !article.properties[key],
    );
    if (missing.length > 0) {
      add({
        rule: "article_schema_incomplete",
        category: "schema",
        severity: "medium",
        summary: "Article schema is missing required properties",
        detail:
          "Author and publication date are the properties Google reads as provenance for an" +
          " article. Without them the markup carries no authorship signal.",
        fixHint: `Populate ${missing.join(", ")} in the Article JSON-LD.`,
        evidence: { missing },
      });
    }
  }

  // --- E-E-A-T. Only what is actually readable from markup; anything softer
  // would be a guess dressed up as a finding.
  if ((pageType === "article" || pageType === "recipe") && !snapshot.hasAuthor) {
    add({
      rule: "missing_author_signal",
      category: "eeat",
      severity: "high",
      summary: "No author attribution",
      detail:
        "Nothing on this page names who wrote it, in the visible markup or the structured" +
        " data. Experience and expertise are assessed per author, so unattributed content" +
        " starts from nothing on the two signals it is most judged by.",
      fixHint:
        "Show a byline linking to an author page, and set `author` in the JSON-LD for this" +
        " route.",
    });
  }

  if ((pageType === "article" || pageType === "recipe") && !snapshot.hasPublishedDate) {
    add({
      rule: "missing_published_date",
      category: "eeat",
      severity: "medium",
      summary: "No publication date",
      detail:
        "Neither a <time datetime> element nor a datePublished property is present, so there" +
        " is no way to tell how current this is. Freshness is a ranking input for produce" +
        " and seasonal content in particular.",
      fixHint: "Render <time datetime> for the published date and set datePublished in JSON-LD.",
    });
  }

  if (
    pageType === "product" &&
    !snapshot.internalLinks.some((link) => link.startsWith("/farms/"))
  ) {
    add({
      rule: "product_missing_farm_attribution",
      category: "eeat",
      severity: "low",
      summary: "Product does not link to the farm that grew it",
      detail:
        "Provenance is this shop's strongest differentiator and its clearest trust signal." +
        " A product page with no link to its farm leaves that unstated to both readers and" +
        " crawlers.",
      fixHint:
        "Link the product's farm on this page, and attribute the farm in the Product JSON-LD.",
    });
  }

  // --- Content and snippet quality.
  if (!snapshot.title) {
    add({
      rule: "title_missing",
      category: "content",
      severity: "high",
      summary: "No <title>",
      detail:
        "The title is both the strongest on-page ranking signal and the clickable line in the" +
        " result. Without one, search engines invent it from the page content.",
      fixHint: "Add a title to this route's meta export.",
    });
  } else if (snapshot.title.length > TITLE_MAX) {
    add({
      rule: "title_too_long",
      category: "content",
      severity: "low",
      summary: `Title is ${snapshot.title.length} characters`,
      detail: `Titles past roughly ${TITLE_MAX} characters get truncated in results, so the end of this one will not be read.`,
      fixHint: `Shorten the title to about ${TITLE_MAX} characters, keeping the distinctive words first.`,
      evidence: { title: snapshot.title, length: snapshot.title.length },
    });
  } else if (snapshot.title.length < TITLE_MIN) {
    add({
      rule: "title_too_short",
      category: "content",
      severity: "low",
      summary: `Title is only ${snapshot.title.length} characters`,
      detail: "A very short title wastes the most valuable line in the search result.",
      fixHint: "Expand the title with what makes this page distinct.",
      evidence: { title: snapshot.title },
    });
  }

  if (!snapshot.metaDescription) {
    add({
      rule: "meta_description_missing",
      category: "content",
      severity: "medium",
      summary: "No meta description",
      detail:
        "With no description, the snippet is assembled from whatever text the crawler finds" +
        " first, which on a commerce page is often navigation.",
      fixHint: "Add a description to this route's meta export.",
    });
  } else if (snapshot.metaDescription.length > META_DESCRIPTION_MAX) {
    add({
      rule: "meta_description_too_long",
      category: "content",
      severity: "low",
      summary: `Meta description is ${snapshot.metaDescription.length} characters`,
      detail: `Descriptions past roughly ${META_DESCRIPTION_MAX} characters are cut off mid-sentence.`,
      fixHint: `Trim to about ${META_DESCRIPTION_MAX} characters.`,
      evidence: { length: snapshot.metaDescription.length },
    });
  } else if (snapshot.metaDescription.length < META_DESCRIPTION_MIN) {
    add({
      rule: "meta_description_too_short",
      category: "content",
      severity: "low",
      summary: `Meta description is only ${snapshot.metaDescription.length} characters`,
      detail: "A very short description leaves most of the snippet to be filled in automatically.",
      fixHint: `Expand toward ${META_DESCRIPTION_MAX} characters.`,
    });
  }

  if (snapshot.h1Count === 0) {
    add({
      rule: "h1_missing",
      category: "content",
      severity: "medium",
      summary: "No <h1>",
      detail:
        "The h1 states what the page is about in its own markup. Nothing else substitutes for it.",
      fixHint: "Give the page a single h1 naming the product, article or category.",
    });
  } else if (snapshot.h1Count > 1) {
    add({
      rule: "h1_multiple",
      category: "content",
      severity: "low",
      summary: `${snapshot.h1Count} <h1> elements`,
      detail:
        "More than one top-level heading blurs what the page is primarily about. Usually the" +
        " extra ones are a site title or a promo block that should be lower in the hierarchy.",
      fixHint: "Keep one h1 and demote the rest to h2.",
      evidence: { count: snapshot.h1Count },
    });
  }

  if (snapshot.imagesWithoutAlt > 0) {
    add({
      rule: "images_missing_alt",
      category: "content",
      severity: "low",
      summary: `${snapshot.imagesWithoutAlt} image(s) with no alt attribute`,
      detail:
        "Missing alt text is an accessibility failure first and lost image-search traffic" +
        " second. An empty alt is fine for decorative images; the attribute being absent" +
        " entirely is not.",
      fixHint: 'Set alt text on these images, or alt="" if they are purely decorative.',
      evidence: { count: snapshot.imagesWithoutAlt },
    });
  }

  if (DETAIL_TYPES.includes(pageType) && snapshot.wordCount < THIN_CONTENT_WORDS) {
    add({
      rule: "thin_content",
      category: "content",
      severity: "medium",
      summary: `Only ${snapshot.wordCount} words of body copy`,
      detail:
        "There is very little here for a crawler to understand the page from, and pages this" +
        " thin are the ones most often crawled and then left unindexed.",
      fixHint: "Expand the description with sourcing, use and storage detail.",
      evidence: { wordCount: snapshot.wordCount },
    });
  }

  return findings;
}

/**
 * Findings that need the whole crawl.
 *
 * `sitemapPaths` is the set the crawl was asked to visit. It matters
 * separately from `snapshots`: a page can be reachable by link and absent from
 * the sitemap, or the reverse, and those are different problems.
 */
export function evaluateCrawl(snapshots: PageSnapshot[], sitemapPaths: Set<string>): Finding[] {
  const findings: Finding[] = [];
  const byPath = new Map(snapshots.map((snapshot) => [snapshot.path, snapshot]));

  // Inbound link counts, for orphan detection. A page linking to itself does
  // not rescue it from being an orphan, so self-links are excluded.
  const inbound = new Map<string, number>();
  for (const snapshot of snapshots) {
    for (const target of snapshot.internalLinks) {
      if (target === snapshot.path) continue;
      inbound.set(target, (inbound.get(target) ?? 0) + 1);
    }
  }

  // Broken internal links, reported once per (source, target) pair so a
  // sitewide footer link to a dead page does not produce one finding per page.
  const brokenTargets = new Map<string, string[]>();
  for (const snapshot of snapshots) {
    for (const target of snapshot.internalLinks) {
      const targetSnapshot = byPath.get(target);
      if (targetSnapshot && targetSnapshot.statusCode >= 400) {
        const sources = brokenTargets.get(target) ?? [];
        sources.push(snapshot.path);
        brokenTargets.set(target, sources);
      }
    }
  }
  for (const [target, sources] of brokenTargets) {
    findings.push({
      rule: "broken_internal_link",
      category: "links",
      severity: "high",
      path: target,
      pageType: byPath.get(target)?.pageType ?? "other",
      summary: `${sources.length} page(s) link to a URL that fails`,
      detail:
        `${target} returns ${byPath.get(target)?.statusCode ?? "an error"} but is linked from` +
        ` ${sources.slice(0, 5).join(", ")}${sources.length > 5 ? ", and others" : ""}.` +
        " Broken internal links waste crawl budget and dead-end readers.",
      fixHint: "Repoint or remove these links, or restore the target page.",
      evidence: { sources: sources.slice(0, 20), statusCode: byPath.get(target)?.statusCode },
    });
  }

  for (const snapshot of snapshots) {
    if (snapshot.statusCode >= 400) continue;

    // Orphans: in the sitemap, but nothing links to them. The crawler reached
    // it only because the sitemap named it, which is exactly how a page ends
    // up crawled and never ranked.
    if (sitemapPaths.has(snapshot.path) && (inbound.get(snapshot.path) ?? 0) === 0) {
      findings.push({
        rule: "orphan_page",
        category: "links",
        severity: "medium",
        path: snapshot.path,
        pageType: snapshot.pageType,
        summary: "No internal links point to this page",
        detail:
          "This URL is only reachable through the sitemap. Pages with no inbound internal" +
          " links receive no link equity and are consistently the last to be indexed, which" +
          " is a common reason a page sits in Search Console as discovered but not indexed.",
        fixHint:
          "Link it from a relevant category, collection or related-items block so it sits in" +
          " the site's structure rather than beside it.",
      });
    }

    // Links pointing at pages that exclude themselves from the index.
    const noindexTargets = snapshot.internalLinks.filter((target) => {
      const targetSnapshot = byPath.get(target);
      return targetSnapshot !== undefined && targetSnapshot.robots.includes("noindex");
    });
    if (noindexTargets.length > 3) {
      findings.push({
        rule: "many_links_to_noindex",
        category: "links",
        severity: "low",
        path: snapshot.path,
        pageType: snapshot.pageType,
        summary: `${noindexTargets.length} links point at noindex pages`,
        detail:
          "Most of the internal links on this page lead somewhere search engines are told to" +
          " ignore, so its link equity is largely being spent on nothing.",
        fixHint:
          "Point these at indexable equivalents, or reconsider whether the targets should be noindex.",
        evidence: { targets: noindexTargets.slice(0, 20) },
      });
    }
  }

  // Duplicate titles. Reported against the second and later pages so the
  // original keeps a clean record.
  const byTitle = new Map<string, string[]>();
  for (const snapshot of snapshots) {
    if (!snapshot.title || snapshot.statusCode >= 400) continue;
    const paths = byTitle.get(snapshot.title) ?? [];
    paths.push(snapshot.path);
    byTitle.set(snapshot.title, paths);
  }
  for (const [title, paths] of byTitle) {
    if (paths.length < 2) continue;
    for (const path of paths.slice(1)) {
      findings.push({
        rule: "duplicate_title",
        category: "content",
        severity: "medium",
        path,
        pageType: byPath.get(path)?.pageType ?? "other",
        summary: "Title is identical to another page",
        detail:
          `${paths.length} pages share the title "${title}". Identical titles make the pages` +
          " look like duplicates of each other, and search engines will usually pick one and" +
          " drop the rest.",
        fixHint: "Give each page a title naming what is specific to it.",
        evidence: { title, paths: paths.slice(0, 20) },
      });
    }
  }

  return findings;
}
