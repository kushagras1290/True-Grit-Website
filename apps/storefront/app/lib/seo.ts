import type { SeoDocument } from "@truegrit/contracts";

const SITE_NAME = "True Grit";

/** Build route `meta` entries from a backend-owned SEO document. */
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
    { property: "og:title", content: title },
    { property: "og:description", content: seo.description },
    { property: "og:type", content: "website" },
    { property: "og:site_name", content: SITE_NAME },
  ];
}
