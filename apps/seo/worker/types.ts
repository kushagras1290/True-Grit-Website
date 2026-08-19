/**
 * Shared shapes for the SEO audit crawler.
 *
 * The worker is deliberately split so that the only part touching the network
 * is `crawl.ts`: `extract.ts` turns a Response into a plain `PageSnapshot`, and
 * `rules.ts` turns snapshots into findings without knowing that HTTP exists.
 * Both of those are then testable with fixtures and no Worker runtime, which is
 * the same reason the support bot's pipeline avoided a model binding.
 */

export interface Env {
  DB: D1Database;
  /** Origin the crawl starts from, e.g. `https://www.truegritin.com`. */
  SITE_ORIGIN: string;
  /** Optional: a GitHub token enables the "open a fix PR" action. */
  GITHUB_TOKEN?: string;
  GITHUB_REPO?: string;
}

/** Route families the rules reason about. Derived from the path in
 *  `pageTypeFor`, so a rule can say "every product page needs Product schema"
 *  without repeating route patterns. */
export type PageType =
  | "home"
  | "product"
  | "category"
  | "article"
  | "recipe"
  | "farm"
  | "bundle"
  | "collection"
  | "policy"
  | "other";

export type Severity = "critical" | "high" | "medium" | "low";
export type Category = "schema" | "eeat" | "links" | "indexing" | "content";

/** Everything one page told us, flattened. Anything a rule needs must be here:
 *  rules never re-fetch. */
export interface PageSnapshot {
  path: string;
  statusCode: number;
  pageType: PageType;
  title: string;
  /** Text of the first h1, used as the heading signal for keyword extraction. */
  h1: string;
  /** Section headings (h2), which is where a content structure shows: an FAQ
   *  block, a storage section, a sourcing section. Comparing these across
   *  competitors is what surfaces a section we are missing entirely. */
  headings: string[];
  metaDescription: string;
  canonical: string;
  robots: string;
  h1Count: number;
  wordCount: number;
  imagesWithoutAlt: number;
  /** `@type` values pulled out of every JSON-LD block on the page. */
  schemaTypes: string[];
  /** Blocks that failed to parse. One malformed block invalidates itself
   *  silently in search consoles, so it is worth reporting separately from
   *  "no schema at all". */
  malformedSchemaBlocks: number;
  /** Parsed JSON-LD objects, so a rule can check required properties rather
   *  than only presence. */
  schemaObjects: SchemaObject[];
  hasAuthor: boolean;
  hasPublishedDate: boolean;
  /** Internal link targets, normalised to paths and deduplicated. */
  internalLinks: string[];
  externalLinkCount: number;
}

export interface SchemaObject {
  type: string;
  /** Only the properties the rules check; the rest is not worth carrying. */
  properties: Record<string, unknown>;
}

export interface Finding {
  rule: string;
  category: Category;
  severity: Severity;
  path: string;
  pageType: PageType;
  summary: string;
  detail: string;
  fixHint: string;
  evidence?: Record<string, unknown>;
}

export interface CrawlRun {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  trigger: "cron" | "manual";
  baseUrl: string;
  pagesDiscovered: number;
  pagesCrawled: number;
  pagesFailed: number;
}

/** Routes that sit under a detail-page prefix without being one. Checked
 *  before the prefix table, because `/farms/partner` is an application form
 *  and would otherwise be audited as a farm profile and told off for having
 *  no farm schema. The storefront's own router orders these first for the
 *  same reason (see apps/storefront/app/routes.ts). */
const EXACT_PATH_TYPES = new Map<string, PageType>([
  ["/farms/partner", "other"],
  ["/recipes/submit", "other"],
  ["/blog/submit", "other"],
  ["/community/new", "other"],
]);

/** Path prefix -> page type, for genuine detail routes. */
const PAGE_TYPE_PREFIXES: Array<[string, PageType]> = [
  ["/product/", "product"],
  ["/category/", "category"],
  ["/blog/", "article"],
  ["/recipes/", "recipe"],
  ["/farms/", "farm"],
  ["/bundles/", "bundle"],
  ["/collections/", "collection"],
];

const POLICY_PATHS = new Set([
  "/returns",
  "/delivery",
  "/privacy",
  "/terms",
  "/standards",
  "/about",
  "/help",
  "/contact",
]);

export function pageTypeFor(path: string): PageType {
  if (path === "/" || path === "") return "home";
  const exact = EXACT_PATH_TYPES.get(path);
  if (exact) return exact;
  if (POLICY_PATHS.has(path)) return "policy";
  for (const [prefix, type] of PAGE_TYPE_PREFIXES) {
    // A bare `/product/` with no slug is a listing, not a detail page, so the
    // prefix has to be followed by something.
    if (path.startsWith(prefix) && path.length > prefix.length) return type;
  }
  return "other";
}

/** Stable identity for a finding across runs: the same problem on the same
 *  page must resolve to the same string every time, or the queue fills with
 *  duplicates and `firstSeenAt` stops meaning anything. */
export function fingerprintFor(rule: string, path: string): string {
  return `${rule}::${path}`;
}
