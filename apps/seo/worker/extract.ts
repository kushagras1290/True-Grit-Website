/**
 * Response -> `PageSnapshot`, using HTMLRewriter.
 *
 * HTMLRewriter is a streaming parser, which is why this is written the way it
 * is rather than as a set of DOM queries. Two consequences shape every handler
 * below:
 *
 * 1. **Text arrives in chunks.** A `text` handler fires several times for one
 *    text node, and only the chunk with `lastInTextNode` set closes it. Every
 *    accumulator here appends and only interprets the buffer once the node
 *    ends; reading a chunk in isolation gives you half a title.
 * 2. **There is no going back.** Elements are seen once, in document order, so
 *    anything cross-cutting (does this page link to itself? does the canonical
 *    disagree with the sitemap?) is decided later in `rules.ts` from the
 *    finished snapshot, not here.
 *
 * The extractor is deliberately total: a page that is malformed, truncated or
 * not HTML at all still produces a snapshot, because "this page is broken" is
 * a finding worth reporting and throwing would lose the whole crawl instead.
 */

import { type PageSnapshot, type SchemaObject, pageTypeFor } from "./types";

/** Only the JSON-LD properties the rules actually check. Carrying whole
 *  documents would put arbitrary page content into D1 for no benefit. */
const KEPT_SCHEMA_PROPERTIES = [
  "name",
  "headline",
  "image",
  "author",
  "datePublished",
  "dateModified",
  "offers",
  "price",
  "priceCurrency",
  "availability",
  "recipeIngredient",
  "recipeInstructions",
  "aggregateRating",
  "review",
  "itemListElement",
  "publisher",
  "description",
] as const;

/** Attribute values that mark a byline without needing rendered text. */
const AUTHOR_SELECTORS = [
  '[rel="author"]',
  '[itemprop="author"]',
  ".author",
  ".byline",
  "[data-author]",
];

class TextBuffer {
  private chunks: string[] = [];
  private done = false;

  append(chunk: string, last: boolean): void {
    if (this.done) return;
    this.chunks.push(chunk);
    if (last) this.done = true;
  }

  get value(): string {
    return this.chunks.join("").replace(/\s+/g, " ").trim();
  }
}

/**
 * Resolve an href against the page and keep it only if it stays on this site.
 *
 * Returns null for anything not worth checking: other origins, `mailto:`,
 * `tel:`, fragments, and query-only links. Fragments are dropped rather than
 * kept because `/returns#refunds` and `/returns` are the same document for
 * every check here, and keeping both would double-count links and report the
 * same broken target twice.
 */
export function normaliseInternalHref(href: string, origin: string): string | null {
  const trimmed = href.trim();
  if (!trimmed || trimmed.startsWith("#")) return null;
  if (/^(mailto:|tel:|javascript:|data:)/i.test(trimmed)) return null;

  let url: URL;
  try {
    url = new URL(trimmed, origin);
  } catch {
    return null;
  }
  if (url.origin !== new URL(origin).origin) return null;

  // Trailing slashes are not significant on this site's routes, so they are
  // normalised away; otherwise `/shop` and `/shop/` look like two pages and
  // one of them appears to be an orphan.
  let path = url.pathname;
  if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
  return path || "/";
}

function collectSchemaObjects(raw: string, into: SchemaObject[]): boolean {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return false;
  }

  // A block may be a single object, an array, or a @graph wrapper. All three
  // are valid JSON-LD and all three appear on this site.
  const queue: unknown[] = [parsed];
  while (queue.length > 0) {
    const node = queue.shift();
    if (Array.isArray(node)) {
      queue.push(...node);
      continue;
    }
    if (!node || typeof node !== "object") continue;
    const record = node as Record<string, unknown>;
    if (Array.isArray(record["@graph"])) queue.push(...record["@graph"]);

    const rawType = record["@type"];
    const types = Array.isArray(rawType) ? rawType : [rawType];
    for (const type of types) {
      if (typeof type !== "string") continue;
      const properties: Record<string, unknown> = {};
      for (const key of KEPT_SCHEMA_PROPERTIES) {
        if (key in record) properties[key] = record[key];
      }
      into.push({ type, properties });
    }
  }
  return true;
}

export async function extractPage(
  response: Response,
  path: string,
  origin: string,
): Promise<PageSnapshot> {
  const title = new TextBuffer();
  const schemaBuffers: TextBuffer[] = [];
  const paragraphs: string[] = [];

  const h1Text = new TextBuffer();
  const headingBuffers: TextBuffer[] = [];

  let metaDescription = "";
  let canonical = "";
  let robots = "";
  let h1Count = 0;
  let imagesWithoutAlt = 0;
  let hasAuthor = false;
  let hasPublishedDate = false;
  let externalLinkCount = 0;
  const internalLinks = new Set<string>();

  const rewriter = new HTMLRewriter()
    .on("title", {
      text(chunk) {
        title.append(chunk.text, chunk.lastInTextNode);
      },
    })
    .on("meta", {
      element(element) {
        const name = (element.getAttribute("name") ?? "").toLowerCase();
        const content = element.getAttribute("content") ?? "";
        if (name === "description") metaDescription = content.trim();
        if (name === "robots") robots = content.trim().toLowerCase();
      },
    })
    .on("link", {
      element(element) {
        const rel = (element.getAttribute("rel") ?? "").toLowerCase();
        if (rel === "canonical") canonical = (element.getAttribute("href") ?? "").trim();
      },
    })
    .on("h1", {
      element() {
        h1Count += 1;
      },
      text(chunk) {
        // Only the first h1's text is kept. A page with several has a finding
        // raised about it anyway, and concatenating them would produce a
        // heading string that appears nowhere on the page.
        h1Text.append(chunk.text, chunk.lastInTextNode);
      },
    })
    // Section headings are what reveal a content structure a rival has and we
    // do not: an FAQ block, a storage section, a "how it is made" section.
    // Captured for competitors, and equally for our own pages so the
    // comparison has both sides.
    .on("h2", {
      element() {
        headingBuffers.push(new TextBuffer());
      },
      text(chunk) {
        headingBuffers[headingBuffers.length - 1]?.append(chunk.text, chunk.lastInTextNode);
      },
    })
    .on("img", {
      element(element) {
        // An empty alt is a deliberate "decorative" signal and is correct; a
        // missing attribute is the accessibility and image-SEO problem.
        if (element.getAttribute("alt") === null) imagesWithoutAlt += 1;
      },
    })
    .on("a", {
      element(element) {
        const href = element.getAttribute("href");
        if (!href) return;
        const internal = normaliseInternalHref(href, origin);
        if (internal === null) {
          if (/^https?:/i.test(href.trim())) externalLinkCount += 1;
          return;
        }
        internalLinks.add(internal);
      },
    })
    .on('script[type="application/ld+json"]', {
      element() {
        schemaBuffers.push(new TextBuffer());
      },
      text(chunk) {
        schemaBuffers[schemaBuffers.length - 1]?.append(chunk.text, chunk.lastInTextNode);
      },
    })
    .on("p", {
      text(chunk) {
        // Word count is an approximation over body copy, used only to spot
        // thin pages, so paragraph text is enough and avoids counting nav and
        // footer boilerplate on every page.
        if (chunk.text.trim()) paragraphs.push(chunk.text);
      },
    })
    .on("time", {
      element(element) {
        if (element.getAttribute("datetime")) hasPublishedDate = true;
      },
    });

  for (const selector of AUTHOR_SELECTORS) {
    rewriter.on(selector, {
      element() {
        hasAuthor = true;
      },
    });
  }

  // The body has to be consumed for the handlers to fire. `arrayBuffer()`
  // drains it without materialising a string we would then throw away.
  await rewriter.transform(response).arrayBuffer();

  const schemaObjects: SchemaObject[] = [];
  let malformedSchemaBlocks = 0;
  for (const buffer of schemaBuffers) {
    const raw = buffer.value;
    if (!raw) continue;
    if (!collectSchemaObjects(raw, schemaObjects)) malformedSchemaBlocks += 1;
  }

  // Authorship also counts if the JSON-LD declares it, even when the visible
  // markup carries no recognisable byline class.
  if (schemaObjects.some((object) => object.properties.author)) hasAuthor = true;
  if (schemaObjects.some((object) => object.properties.datePublished)) hasPublishedDate = true;

  return {
    path,
    statusCode: response.status,
    pageType: pageTypeFor(path),
    title: title.value,
    h1: h1Text.value,
    headings: headingBuffers
      .map((buffer) => buffer.value)
      .filter((heading) => heading.length > 2 && heading.length < 120),
    metaDescription,
    canonical,
    robots,
    h1Count,
    wordCount: paragraphs.join(" ").split(/\s+/).filter(Boolean).length,
    imagesWithoutAlt,
    schemaTypes: [...new Set(schemaObjects.map((object) => object.type))],
    malformedSchemaBlocks,
    schemaObjects,
    hasAuthor,
    hasPublishedDate,
    internalLinks: [...internalLinks],
    externalLinkCount,
  };
}
