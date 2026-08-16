import type { SeoDocument } from "@truegrit/contracts";

import type { RouteSeoOverride } from "./catalogue.server";
import { EN_MESSAGES, type LocaleMessages, type ResolvedMessages } from "./i18n/messages";
import { translateSource } from "./i18n/localized-text";

const SITE_NAME = "True Grit";
export const SITE_ORIGIN = "https://www.truegritin.com";
export const DEFAULT_SITE_DESCRIPTION =
  "Shop traceable organic food from True Grit — traditional grains, stone-ground flours, pulses, seeds and cold-pressed oils sourced directly from trusted farms.";

export function absoluteSiteUrl(pathOrUrl: string | null | undefined): string {
  const value = pathOrUrl?.trim() || "/";
  try {
    return new URL(value, SITE_ORIGIN).href;
  } catch {
    return `${SITE_ORIGIN}/`;
  }
}

/**
 * The resolved catalogue for the current request, read out of the root match.
 *
 * `meta()` runs outside React, so it cannot use the locale context that every
 * component relies on — which is why page titles stayed English in every
 * language while the page body translated. The root loader already ships the
 * chosen locale's entries to render the app; this reads the same payload so the
 * `<title>`, description and Open Graph tags travel with the rest of the page.
 */
export type MetaMatches = readonly ({ data?: unknown } | undefined)[];

export function metaMessages(matches: MetaMatches | undefined): ResolvedMessages {
  const rootData = matches?.[0]?.data as { messages?: LocaleMessages } | undefined;
  if (!rootData?.messages) return EN_MESSAGES;
  return { ...EN_MESSAGES, ...rootData.messages };
}

/** Merge an admin-saved route SEO override onto a route's hardcoded fallback
 * metadata — same idea as a CMS page's own `seo` object taking priority over
 * `fallbackSeo`, for routes that have no CMS page record to carry it on. */
export function mergeRouteSeo(
  override: RouteSeoOverride | null | undefined,
  fallback: SeoDocument,
): SeoDocument {
  if (!override) return fallback;
  return {
    title: override.seoTitle || fallback.title,
    description: override.seoDescription || fallback.description,
    keywords: override.seoKeywords || fallback.keywords,
    indexing: override.indexingPolicy,
    canonicalPath: fallback.canonicalPath,
  };
}

/** Build route `meta` entries from a backend-owned SEO document. Emits a
 * root-relative `<link rel="canonical">` alongside the usual meta tags —
 * search engines resolve it against the page's own URL, so this correctly
 * de-duplicates trailing slashes and query params without needing the
 * deployment's absolute origin threaded through every route loader. */
export function seoMeta(
  seo: SeoDocument | null | undefined,
  /** Route `meta()` receives these; pass them through so the tags translate.
   *  Omitted (or on a route with no root data) the copy stays English, which is
   *  the same fallback the rest of the catalogue uses. */
  matches?: MetaMatches,
) {
  if (!seo) {
    return [{ title: SITE_NAME }, { name: "robots", content: "noindex" }];
  }
  const messages = metaMessages(matches);
  const localizedTitle = translateSource(messages, seo.title);
  const description = translateSource(messages, seo.description).trim() || DEFAULT_SITE_DESCRIPTION;
  const title = localizedTitle.includes(SITE_NAME)
    ? localizedTitle
    : `${localizedTitle} · ${SITE_NAME}`;
  return [
    { title },
    { name: "description", content: description },
    ...(seo.keywords ? [{ name: "keywords", content: seo.keywords }] : []),
    { name: "robots", content: seo.indexing === "index" ? "index, follow" : "noindex, nofollow" },
    {
      tagName: "link" as const,
      rel: "canonical",
      href: absoluteSiteUrl(seo.canonicalPath),
    },
    { property: "og:title", content: title },
    { property: "og:description", content: description },
    { property: "og:type", content: "website" },
    { property: "og:site_name", content: SITE_NAME },
  ];
}

/** JSON-LD structured data for an Article (blog post). Rendered as a
 * `<script type="application/ld+json">` meta entry — React Router's meta()
 * supports raw script descriptors the same way it supports link/meta tags. */
export function articleJsonLd(article: {
  title: string;
  excerpt: string;
  authorName: string;
  publishedAt: string;
  canonicalPath: string;
  imageUrl?: string;
}) {
  return {
    "script:ld+json": {
      "@context": "https://schema.org",
      "@type": "Article",
      headline: article.title,
      description: article.excerpt,
      author: { "@type": "Person", name: article.authorName },
      datePublished: article.publishedAt,
      mainEntityOfPage: absoluteSiteUrl(article.canonicalPath),
      ...(article.imageUrl ? { image: absoluteSiteUrl(article.imageUrl) } : {}),
    },
  };
}

/** JSON-LD structured data for a Recipe. */
/** Longest a derived `HowToStep.name` may run before it stops reading as a
 *  summary. Google's guidance is that `name` must not simply restate `text`. */
const MAX_STEP_NAME_LENGTH = 60;

export function recipeStepAnchor(index: number): string {
  return `step-${index + 1}`;
}

/**
 * A short label for a method step, or `null` when the step cannot yield one.
 *
 * Steps are stored as free prose with no separate heading, so the first
 * sentence is the only summary available. A single-sentence step has nothing
 * to summarise -- emitting `name` there would duplicate `text`, which Google
 * calls out specifically -- so those return `null` and the field is omitted.
 */
function summariseStep(step: string): string | null {
  const text = step.trim();
  const firstSentence = /^.*?[.!?](?=\s|$)/.exec(text)?.[0]?.trim();
  if (!firstSentence || firstSentence.length === text.length) return null;
  if (firstSentence.length <= MAX_STEP_NAME_LENGTH) return firstSentence;
  const clipped = firstSentence.slice(0, MAX_STEP_NAME_LENGTH);
  const lastSpace = clipped.lastIndexOf(" ");
  return `${lastSpace > 0 ? clipped.slice(0, lastSpace) : clipped}...`;
}

export function recipeJsonLd(recipe: {
  title: string;
  excerpt: string;
  prepMinutes: number;
  cookMinutes: number;
  servings: number;
  ingredients: Array<{ label: string; quantityText: string }>;
  steps: string[];
  canonicalPath: string;
  imageUrl?: string;
  dietaryTags?: string[];
  keywords?: string | null;
  cuisine?: string | null;
}) {
  const canonical = absoluteSiteUrl(recipe.canonicalPath);
  // `seo.keywords` is editor-supplied and therefore the better signal; the
  // dietary tags are a real fallback rather than an invented one.
  const keywords = recipe.keywords?.trim() || (recipe.dietaryTags ?? []).join(", ");
  return {
    "script:ld+json": {
      "@context": "https://schema.org",
      "@type": "Recipe",
      name: recipe.title,
      description: recipe.excerpt,
      prepTime: `PT${recipe.prepMinutes}M`,
      cookTime: `PT${recipe.cookMinutes}M`,
      // Google reads `totalTime` separately from the two parts and does not
      // add them up itself, so an explicit sum is what makes the cook-time
      // filter work in search results.
      totalTime: `PT${recipe.prepMinutes + recipe.cookMinutes}M`,
      recipeYield: `${recipe.servings} servings`,
      // Omitted rather than defaulted: a site-wide fallback would publish
      // "Indian" over a recipe written for another market, and a false claim in
      // structured data is worse than a missing optional field.
      ...(recipe.cuisine?.trim() ? { recipeCuisine: recipe.cuisine.trim() } : {}),
      // Named as the publisher, which is what these are: brand-published
      // recipes with no individual byline in the CMS. The `@id` matches the
      // Organization node on the home page so the two merge into one entity
      // rather than reading as two different publishers with the same name.
      author: {
        "@type": "Organization",
        "@id": `${SITE_ORIGIN}/#organization`,
        name: SITE_NAME,
        url: `${SITE_ORIGIN}/`,
      },
      recipeIngredient: recipe.ingredients.map((ingredient) =>
        `${ingredient.quantityText} ${ingredient.label}`.trim(),
      ),
      recipeInstructions: recipe.steps.map((step, index) => {
        const name = summariseStep(step);
        return {
          "@type": "HowToStep",
          ...(name ? { name } : {}),
          text: step,
          // Resolves to the matching `id` on the rendered step (routes/recipe.tsx),
          // so the deep link Google shows actually lands on that instruction.
          url: `${canonical}#${recipeStepAnchor(index)}`,
        };
      }),
      mainEntityOfPage: canonical,
      ...(keywords ? { keywords } : {}),
      ...(recipe.imageUrl ? { image: absoluteSiteUrl(recipe.imageUrl) } : {}),
    },
  };
}

export function organizationJsonLd() {
  return {
    "script:ld+json": {
      "@context": "https://schema.org",
      "@type": "Organization",
      "@id": `${SITE_ORIGIN}/#organization`,
      name: SITE_NAME,
      url: `${SITE_ORIGIN}/`,
      logo: `${SITE_ORIGIN}/brand/true-grit-mark.webp`,
    },
  };
}

export function websiteJsonLd() {
  return {
    "script:ld+json": {
      "@context": "https://schema.org",
      "@type": "WebSite",
      "@id": `${SITE_ORIGIN}/#website`,
      name: SITE_NAME,
      url: `${SITE_ORIGIN}/`,
      publisher: { "@id": `${SITE_ORIGIN}/#organization` },
      potentialAction: {
        "@type": "SearchAction",
        target: `${SITE_ORIGIN}/search?q={search_term_string}`,
        "query-input": "required name=search_term_string",
      },
    },
  };
}

export function breadcrumbJsonLd(items: Array<{ name: string; path: string }>) {
  return {
    "script:ld+json": {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: items.map((item, index) => ({
        "@type": "ListItem",
        position: index + 1,
        name: item.name,
        item: absoluteSiteUrl(item.path),
      })),
    },
  };
}

export function productJsonLd(product: {
  name: string;
  description: string;
  canonicalPath: string;
  sku?: string;
  priceMinor: number;
  currencyCode: string;
  availability: "in_stock" | "low_stock" | "out_of_stock";
  imageUrl?: string | null;
}) {
  const availability =
    product.availability === "out_of_stock"
      ? "https://schema.org/OutOfStock"
      : product.availability === "low_stock"
        ? "https://schema.org/LimitedAvailability"
        : "https://schema.org/InStock";
  return {
    "script:ld+json": {
      "@context": "https://schema.org",
      "@type": "Product",
      name: product.name,
      description: product.description,
      url: absoluteSiteUrl(product.canonicalPath),
      brand: { "@type": "Brand", name: SITE_NAME },
      ...(product.sku ? { sku: product.sku } : {}),
      ...(product.imageUrl ? { image: absoluteSiteUrl(product.imageUrl) } : {}),
      offers: {
        "@type": "Offer",
        url: absoluteSiteUrl(product.canonicalPath),
        priceCurrency: product.currencyCode,
        price: (product.priceMinor / 100).toFixed(2),
        availability,
        itemCondition: "https://schema.org/NewCondition",
        seller: { "@id": `${SITE_ORIGIN}/#organization` },
      },
    },
  };
}
