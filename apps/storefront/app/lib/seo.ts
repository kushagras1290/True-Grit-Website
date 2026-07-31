import type { SeoDocument } from "@truegrit/contracts";

import type { RouteSeoOverride } from "./catalogue.server";

const SITE_NAME = "True Grit";

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
export function seoMeta(seo: SeoDocument | null | undefined) {
  if (!seo) {
    return [{ title: SITE_NAME }, { name: "robots", content: "noindex" }];
  }
  const title = seo.title.includes(SITE_NAME) ? seo.title : `${seo.title} · ${SITE_NAME}`;
  return [
    { title },
    { name: "description", content: seo.description },
    ...(seo.keywords ? [{ name: "keywords", content: seo.keywords }] : []),
    { name: "robots", content: seo.indexing === "index" ? "index, follow" : "noindex, nofollow" },
    { tagName: "link" as const, rel: "canonical", href: seo.canonicalPath },
    { property: "og:title", content: title },
    { property: "og:description", content: seo.description },
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
      mainEntityOfPage: article.canonicalPath,
      ...(article.imageUrl ? { image: article.imageUrl } : {}),
    },
  };
}

/** JSON-LD structured data for a Recipe. */
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
}) {
  return {
    "script:ld+json": {
      "@context": "https://schema.org",
      "@type": "Recipe",
      name: recipe.title,
      description: recipe.excerpt,
      prepTime: `PT${recipe.prepMinutes}M`,
      cookTime: `PT${recipe.cookMinutes}M`,
      recipeYield: `${recipe.servings} servings`,
      recipeIngredient: recipe.ingredients.map((ingredient) =>
        `${ingredient.quantityText} ${ingredient.label}`.trim(),
      ),
      recipeInstructions: recipe.steps.map((step) => ({ "@type": "HowToStep", text: step })),
      mainEntityOfPage: recipe.canonicalPath,
      ...(recipe.imageUrl ? { image: recipe.imageUrl } : {}),
    },
  };
}
