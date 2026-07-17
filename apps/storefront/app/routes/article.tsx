import { data } from "react-router";

import type { Route } from "./+types/article";
import { Breadcrumbs } from "../components/catalogue";
import { CmsBlock, type BlockData } from "../components/blocks";
import { catalogueRuntime, loadArticle, loadFarms, loadProductsBySlugs } from "../lib/catalogue.server";
import { resolveCountry } from "../lib/geo.server";
import { articleJsonLd, seoMeta } from "../lib/seo";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const runtime = catalogueRuntime(context);
  const article = await loadArticle(params.slug, runtime);
  if (!article) throw data("Article not found", { status: 404 });
  const productSlugs = article.blocks.flatMap((block) =>
    block.type === "product_collection" ? block.props.productSlugs : [],
  );
  const [products, farms] = await Promise.all([
    loadProductsBySlugs(productSlugs, resolveCountry(request), runtime),
    loadFarms(runtime),
  ]);
  return { article, products, farms };
}

export function meta({ data: loaderData }: Route.MetaArgs) {
  if (!loaderData) return seoMeta(null);
  return [
    ...seoMeta(loaderData.article.seo),
    articleJsonLd({
      title: loaderData.article.title,
      excerpt: loaderData.article.excerpt,
      authorName: loaderData.article.authorName,
      publishedAt: loaderData.article.publishedAt,
      canonicalPath: loaderData.article.seo.canonicalPath,
    }),
  ];
}

export default function ArticlePage({ loaderData }: Route.ComponentProps) {
  const { article, products, farms } = loaderData;
  const blockData: BlockData = {
    productsBySlug: new Map(products.map((product) => [product.slug, product])),
    categoriesBySlug: new Map(),
    farmsBySlug: new Map(farms.map((farm) => [farm.slug, farm])),
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
      <article className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
        <header>
          <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
            {article.authorName} · {article.readingMinutes} min read
          </p>
          <h1 className="mt-3 font-display text-3xl leading-tight text-ink md:text-4xl">
            {article.title}
          </h1>
          <p className="mt-3 text-lg text-ink-muted">{article.excerpt}</p>
        </header>

        {article.pullQuote ? (
          <blockquote className="mt-8 border-l-4 border-accent py-1 pl-5 font-display text-xl leading-snug text-brand">
            {article.pullQuote}
          </blockquote>
        ) : null}
      </article>

      {article.blocks.map((block) => (
        <CmsBlock key={block.id} block={block} data={blockData} />
      ))}
    </>
  );
}
