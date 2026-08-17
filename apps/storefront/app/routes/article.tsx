import { data } from "react-router";

import type { Route } from "./+types/article";
import { Breadcrumbs } from "../components/catalogue";
import { CmsBlock, type BlockData } from "../components/blocks";
import { ContentComments } from "../components/content-comments";
import { PageBanner } from "../components/page-banner";
import {
  catalogueRuntime,
  loadArticle,
  loadFarms,
  loadProductsBySlugs,
} from "../lib/catalogue.server";
import { resolveCountry } from "../lib/geo.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { mediaUrl } from "../lib/media";
import { articleJsonLd, breadcrumbJsonLd, seoMeta } from "../lib/seo";
import { useLocalizeFormat } from "../lib/i18n/localized-text";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const runtime = catalogueRuntime(context);
  const { locale } = resolveLocale(request);
  const article = await loadArticle(params.slug, runtime, locale.code);
  if (!article) throw data("Article not found", { status: 404 });
  const productSlugs = article.blocks.flatMap((block) =>
    block.type === "product_collection" ? block.props.productSlugs : [],
  );
  const [products, farms] = await Promise.all([
    loadProductsBySlugs(productSlugs, resolveCountry(request), runtime, locale.code),
    loadFarms(runtime, locale.code),
  ]);
  return { article, products, farms };
}

export function meta({ data: loaderData, matches }: Route.MetaArgs) {
  if (!loaderData) return seoMeta(null, matches);
  return [
    ...seoMeta(loaderData.article.seo, matches),
    articleJsonLd({
      title: loaderData.article.title,
      excerpt: loaderData.article.excerpt,
      authorName: loaderData.article.authorName,
      publishedAt: loaderData.article.publishedAt,
      canonicalPath: loaderData.article.seo.canonicalPath,
      imageUrl: mediaUrl(loaderData.article.heroImageUrl) ?? undefined,
    }),
    breadcrumbJsonLd([
      { name: "Home", path: "/" },
      { name: "Blog", path: "/blog" },
      {
        name: loaderData.article.title,
        path: loaderData.article.seo.canonicalPath,
      },
    ]),
  ];
}

export default function ArticlePage({ loaderData }: Route.ComponentProps) {
  const format = useLocalizeFormat();
  const { article, products, farms } = loaderData;
  const blockData: BlockData = {
    productsBySlug: new Map(products.map((product) => [product.slug, product])),
    categoriesBySlug: new Map(),
    farmsBySlug: new Map(farms.map((farm) => [farm.slug, farm])),
    // Article body content is limited to `ContentBlock` (rich text, product
    // collection, farmer story, FAQ) -- `reviews_showcase`,
    // `promotion_banner` and `recommendations` never appear here.
    reviewsByBlockId: new Map(),
    promotionsByBlockId: new Map(),
    recommendationsByBlockId: new Map(),
  };

  return (
    <>
      <Breadcrumbs
        items={[
          { label: "Home", path: "/" },
          { label: "Blog", path: "/blog" },
          { label: article.title, path: `/blog/${article.slug}` },
        ]}
      />
      {/* Full-bleed and hero-sized, matching the homepage banner and the blog
          index — a post used to open with a boxed 21:9 strip that read as a
          thumbnail rather than a banner. The title lives in the banner, so the
          article body below starts at the byline. */}
      <PageBanner
        imageUrl={article.heroImageUrl || "/content/default-blog.webp"}
        imageAlt={article.heroImageAlt}
        eyebrow={format("{author} · {minutes} min read", {
          author: article.authorName,
          minutes: article.readingMinutes,
        })}
        heading={article.title}
        description={article.excerpt}
      />

      {/* Only rendered when there is a quote — an empty band of padding between
          the banner and the first content block reads as a broken layout. */}
      {article.pullQuote ? (
        <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
          <blockquote className="border-l-4 border-accent py-1 pl-5 font-display text-xl leading-snug text-brand">
            {article.pullQuote}
          </blockquote>
        </div>
      ) : null}

      {article.blocks.map((block) => (
        <CmsBlock key={block.id} block={block} data={blockData} />
      ))}

      <ContentComments contentType="article" slug={article.slug} />
    </>
  );
}
