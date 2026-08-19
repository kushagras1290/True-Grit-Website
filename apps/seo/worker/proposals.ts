/**
 * Proposal generation: findings and keyword gaps -> concrete field changes.
 *
 * This is the part that removes the manual work. A finding says "this product
 * has no meta description"; a proposal says "set `seo_description` on
 * `prd_abc` to this exact string", and the dashboard applies it with one
 * click. Everything below exists to make that click safe.
 *
 * **Nothing is invented.** Every proposed value is assembled from text the
 * entity already owns -- its name, its short description, its farm, its
 * category -- plus a keyword phrase that a competitor demonstrably uses and
 * that already matches this entity's own vocabulary. If an entity has no
 * usable source text, no proposal is generated for it. That is the same
 * fail-closed rule the support bot's templates follow, and for the same
 * reason: a plausible sentence that is not true about the product is worse
 * than a blank field.
 *
 * **Nothing is overwritten silently.** Proposals target empty or defective
 * fields by default. Where an existing value is being replaced (a title over
 * the length limit, a duplicate), the current value is carried on the proposal
 * so the dashboard shows before and after, and the real previous value is
 * captured again at apply time so a revert is exact.
 *
 * **Keyword matching is conservative.** A gap term is only attached to an
 * entity when the term's words already appear in that entity's own name or
 * description. Stuffing "cold pressed" into a product that is not cold pressed
 * would be both a lie and, in SEO terms, actively harmful.
 */

import type { KeywordGap } from "./keywords";

/** A CMS row the agent may propose changes to. */
export interface SeoEntity {
  entityType: "product" | "article" | "recipe" | "category" | "page" | "route";
  entityId: string;
  label: string;
  path: string;
  /** Name or title as shown to customers. */
  name: string;
  /** Whatever prose the row already owns: short description, excerpt. */
  description: string;
  /** Extra factual context that may be used in generated copy, e.g. the farm
   *  or the category. Only values already stored against the entity. */
  context: string[];
  seoTitle: string;
  seoDescription: string;
  seoKeywords: string;
  indexingPolicy: string;
  /**
   * Which columns this table actually has.
   *
   * Not every entity carries every field: `products` and `categories` have no
   * `seo_keywords` column, while `articles`, `recipes`, `pages` and
   * `route_seo_overrides` do. Generating a keyword proposal for a product
   * would produce a row the apply step could only fail on, so the generator
   * is told the shape rather than assuming it.
   */
  supportedFields: ReadonlySet<Proposal["field"]>;
}

/** The columns each entity table really has. Verified against the schema
 *  rather than assumed; see the note on `SeoEntity.supportedFields`. */
export const SUPPORTED_FIELDS: Record<SeoEntity["entityType"], ReadonlySet<Proposal["field"]>> = {
  product: new Set(["seo_title", "seo_description", "indexing_policy"] as const),
  category: new Set(["seo_title", "seo_description", "indexing_policy"] as const),
  article: new Set(["seo_title", "seo_description", "seo_keywords", "indexing_policy"] as const),
  recipe: new Set(["seo_title", "seo_description", "seo_keywords", "indexing_policy"] as const),
  page: new Set(["seo_title", "seo_description", "seo_keywords", "indexing_policy"] as const),
  route: new Set(["seo_title", "seo_description", "seo_keywords", "indexing_policy"] as const),
};

export interface Proposal {
  entityType: SeoEntity["entityType"];
  entityId: string;
  entityLabel: string;
  path: string;
  field: "seo_title" | "seo_description" | "seo_keywords" | "indexing_policy";
  currentValue: string;
  proposedValue: string;
  rationale: string;
  source: "gap" | "finding";
  sourceRef: string;
  confidence: number;
}

const SITE_SUFFIX = "True Grit";
const TITLE_LIMIT = 60;
const DESCRIPTION_LIMIT = 155;
const DESCRIPTION_MIN_SOURCE = 40;
const MAX_KEYWORDS = 6;

function words(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[^a-z0-9\s-]/g, " ")
      .split(/[\s-]+/)
      .filter((word) => word.length > 2),
  );
}

/**
 * Trim to a limit on a word boundary, never mid-word.
 *
 * A meta description cut at exactly 155 characters routinely ends "cold pres",
 * which reads as broken rather than truncated.
 */
function trimTo(text: string, limit: number): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= limit) return clean;
  const cut = clean.slice(0, limit);
  const boundary = cut.lastIndexOf(" ");
  return (boundary > limit * 0.6 ? cut.slice(0, boundary) : cut).replace(/[,;:.\s]+$/, "");
}

/**
 * Gap terms this entity can honestly claim.
 *
 * "Honestly" is the operative constraint: every word of the term must already
 * appear in the entity's own name, description or context. That makes the
 * match a recognition that the entity is about this thing, not an assertion
 * that it should be.
 */
export function matchTerms(
  entity: SeoEntity,
  gaps: KeywordGap[],
  limit = MAX_KEYWORDS,
): KeywordGap[] {
  const vocabulary = words(`${entity.name} ${entity.description} ${entity.context.join(" ")}`);
  if (vocabulary.size === 0) return [];

  return gaps
    .filter((gap) => {
      const termWords = gap.term.split(" ");
      return termWords.every((word) => vocabulary.has(word));
    })
    .slice(0, limit);
}

function titleFor(entity: SeoEntity, matched: KeywordGap[]): string | null {
  if (!entity.name.trim()) return null;

  // The strongest matched phrase that is not already in the name earns its
  // place; otherwise the name plus the site suffix is the honest title.
  const nameWords = words(entity.name);
  const addition = matched.find((gap) => gap.term.split(" ").some((word) => !nameWords.has(word)));

  const withKeyword = addition
    ? `${entity.name} | ${addition.term} | ${SITE_SUFFIX}`
    : `${entity.name} | ${SITE_SUFFIX}`;

  if (withKeyword.length <= TITLE_LIMIT) return withKeyword;
  const withoutKeyword = `${entity.name} | ${SITE_SUFFIX}`;
  if (withoutKeyword.length <= TITLE_LIMIT) return withoutKeyword;
  return trimTo(entity.name, TITLE_LIMIT);
}

function descriptionFor(entity: SeoEntity): string | null {
  // Built only from prose the entity already owns. A product with no
  // description gets no proposal rather than a generated claim about it.
  const source = entity.description.trim();
  if (source.length < DESCRIPTION_MIN_SOURCE) return null;

  const context = entity.context.filter(Boolean).join(", ");
  const base = trimTo(source, DESCRIPTION_LIMIT);
  if (!context) return base;

  const withContext = trimTo(`${source} From ${context}.`, DESCRIPTION_LIMIT);
  return withContext.length > base.length ? withContext : base;
}

/**
 * Every change worth making to one entity.
 *
 * `findingRules` is the set of rules currently open against this entity's
 * path, which is what lets a proposal say "because the crawl found the title
 * is too long" rather than proposing a change nobody asked for.
 */
export function proposalsFor(
  entity: SeoEntity,
  gaps: KeywordGap[],
  findingRules: Set<string>,
): Proposal[] {
  const proposals: Proposal[] = [];
  const matched = matchTerms(entity, gaps);
  const base = {
    entityType: entity.entityType,
    entityId: entity.entityId,
    entityLabel: entity.label,
    path: entity.path,
  };

  // --- Title.
  const titleBroken =
    findingRules.has("title_missing") ||
    findingRules.has("title_too_long") ||
    findingRules.has("duplicate_title");
  if (!entity.seoTitle.trim() || titleBroken) {
    const title = titleFor(entity, matched);
    if (title && title !== entity.seoTitle) {
      proposals.push({
        ...base,
        field: "seo_title",
        currentValue: entity.seoTitle,
        proposedValue: title,
        rationale: !entity.seoTitle.trim()
          ? "No SEO title is set, so search engines are inventing one from the page content."
          : `The crawl flagged this title (${[...findingRules].filter((rule) => rule.startsWith("title") || rule === "duplicate_title").join(", ")}).`,
        source: matched.length > 0 ? "gap" : "finding",
        sourceRef: matched[0]?.term ?? [...findingRules][0] ?? "",
        // A title built around a matched competitor term is a stronger
        // proposal than one that is only the product name.
        confidence: matched.length > 0 ? 0.9 : 0.7,
      });
    }
  }

  // --- Description.
  if (!entity.seoDescription.trim() || findingRules.has("meta_description_too_long")) {
    const description = descriptionFor(entity);
    if (description && description !== entity.seoDescription) {
      proposals.push({
        ...base,
        field: "seo_description",
        currentValue: entity.seoDescription,
        proposedValue: description,
        rationale: !entity.seoDescription.trim()
          ? "No meta description is set, so the snippet is assembled from whatever text the crawler finds first."
          : "The existing description is longer than the snippet can show and is being cut off.",
        source: "finding",
        sourceRef: entity.seoDescription.trim()
          ? "meta_description_too_long"
          : "meta_description_missing",
        confidence: 0.85,
      });
    }
  }

  // --- Keywords. Only ever additive, and only terms the entity can claim.
  if (matched.length > 0) {
    const existing = entity.seoKeywords
      .split(",")
      .map((keyword) => keyword.trim().toLowerCase())
      .filter(Boolean);
    const additions = matched.map((gap) => gap.term).filter((term) => !existing.includes(term));
    if (additions.length > 0) {
      const combined = [...existing, ...additions].slice(0, MAX_KEYWORDS + existing.length);
      proposals.push({
        ...base,
        field: "seo_keywords",
        currentValue: entity.seoKeywords,
        proposedValue: combined.join(", "),
        rationale:
          `${additions.length} phrase(s) competitors build pages around, which this item's own` +
          " name and description already describe.",
        source: "gap",
        sourceRef: additions.join(", "),
        confidence: Math.min(0.6 + additions.length * 0.1, 0.95),
      });
    }
  }

  // --- Indexing. The finding that stops a page existing in search at all, and
  // the one change here with a genuinely large effect, so it is proposed only
  // when the crawl actually observed the contradiction.
  if (findingRules.has("noindex_in_sitemap") && entity.indexingPolicy === "noindex") {
    proposals.push({
      ...base,
      field: "indexing_policy",
      currentValue: entity.indexingPolicy,
      proposedValue: "index",
      rationale:
        "This page is published in the sitemap while telling search engines not to index it," +
        " so it cannot appear in results. Setting it to index resolves the contradiction.",
      source: "finding",
      sourceRef: "noindex_in_sitemap",
      // Deliberately below the others: sometimes noindex is correct and the
      // sitemap is what should change. A human should look at this one.
      confidence: 0.6,
    });
  }

  // Drop anything the entity's table cannot store. Filtering at the end rather
  // than guarding each branch keeps the generation rules readable and means a
  // schema change is one line here.
  return proposals.filter((proposal) => entity.supportedFields.has(proposal.field));
}

/** Normalise a section heading so wording variants collapse together. */
export function headingKey(heading: string): string {
  const normalised = heading
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  // A handful of section names every retailer words differently. Mapping them
  // is what makes "FAQs" and "Frequently asked questions" one gap rather than
  // two unrelated headings.
  const synonyms: Array<[RegExp, string]> = [
    [/^(faqs?|frequently asked questions|common questions|questions)$/, "faq"],
    [/^(how to (use|cook|prepare)|usage|uses|serving suggestions?)$/, "how to use"],
    [/^(storage|how to store|shelf life|keeping it fresh)$/, "storage"],
    [/^(nutrition|nutritional (info|information|value)|nutrition facts)$/, "nutrition"],
    [/^(reviews?|customer reviews?|ratings?|what customers say)$/, "reviews"],
    [/^(sourcing|where it comes from|our farms?|origin|provenance)$/, "sourcing"],
    [/^(delivery|shipping|delivery information)$/, "delivery"],
    [/^(ingredients?|what.s inside|composition)$/, "ingredients"],
  ];
  for (const [pattern, canonical] of synonyms) {
    if (pattern.test(normalised)) return canonical;
  }
  return normalised;
}
