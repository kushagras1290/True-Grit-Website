import { data } from "react-router";

import type { Route } from "./+types/article";
import { Breadcrumbs } from "../components/catalogue";
import { catalogueRuntime, loadArticle } from "../lib/catalogue.server";
import { seoMeta } from "../lib/seo";

export async function loader({ params, context }: Route.LoaderArgs) {
  const article = await loadArticle(params.slug, catalogueRuntime(context));
  if (!article) throw data("Article not found", { status: 404 });
  return { article };
}

export function meta({ data: loaderData }: Route.MetaArgs) {
  return seoMeta(loaderData?.article.seo);
}

export default function ArticlePage({ loaderData }: Route.ComponentProps) {
  const { article } = loaderData;
  const midpoint = Math.ceil(article.body.length / 2);

  return (
    <>
      <Breadcrumbs
        items={[
          { label: "Home", path: "/" },
          { label: "Journal", path: "/journal" },
          { label: article.title, path: `/journal/${article.slug}` },
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

        <div className="mt-8 space-y-5 text-base leading-relaxed text-ink">
          {article.body.slice(0, midpoint).map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
          {article.pullQuote ? (
            <blockquote className="border-l-4 border-accent py-1 pl-5 font-display text-xl leading-snug text-brand">
              {article.pullQuote}
            </blockquote>
          ) : null}
          {article.body.slice(midpoint).map((paragraph, index) => (
            <p key={midpoint + index}>{paragraph}</p>
          ))}
        </div>
      </article>
    </>
  );
}
