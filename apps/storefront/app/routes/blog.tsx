import { Link } from "react-router";

import type { Route } from "./+types/blog";
import { Section } from "../components/catalogue";
import { catalogueRuntime, loadArticles } from "../lib/catalogue.server";
import { seoMeta } from "../lib/seo";

export async function loader({ context }: Route.LoaderArgs) {
  return { articles: await loadArticles(catalogueRuntime(context)) };
}

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Blog",
    description: "Stories about food, farming and eating a little slower.",
    canonicalPath: "/blog",
    indexing: "index",
  });
}

export default function BlogPage({ loaderData }: Route.ComponentProps) {
  return (
    <Section eyebrow="The blog" heading="Stories worth chewing on">
      <div className="mx-auto mb-8 flex max-w-2xl items-center justify-between gap-3">
        <p className="text-sm text-ink-muted">
          Have a story to tell? Pitch a post and our editors will review it.
        </p>
        <Link
          to="/blog/submit"
          className="inline-flex min-h-11 shrink-0 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
        >
          Post a blog
        </Link>
      </div>
      <div className="mx-auto max-w-2xl space-y-8">
        {loaderData.articles.map((article) => (
          <Link
            key={article.id}
            to={`/blog/${article.slug}`}
            className="group block border-t border-line pt-6"
          >
            <p className="text-xs text-ink-muted">
              {article.authorName} · {article.readingMinutes} min read
            </p>
            <h2 className="mt-1.5 font-display text-2xl text-ink group-hover:text-brand">
              {article.title}
            </h2>
            <p className="mt-2 text-base text-ink-muted">{article.excerpt}</p>
          </Link>
        ))}
      </div>
    </Section>
  );
}
