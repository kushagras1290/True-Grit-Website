import { Link } from "react-router";

import type { Route } from "./+types/journal";
import { Section } from "../components/catalogue";
import { loadArticles } from "../lib/catalogue.server";
import { seoMeta } from "../lib/seo";

export async function loader() {
  return { articles: await loadArticles() };
}

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Journal",
    description: "Stories about food, farming and eating a little slower.",
    canonicalPath: "/journal",
    indexing: "index",
  });
}

export default function JournalPage({ loaderData }: Route.ComponentProps) {
  return (
    <Section eyebrow="The journal" heading="Stories worth chewing on">
      <div className="mx-auto max-w-2xl space-y-8">
        {loaderData.articles.map((article) => (
          <Link key={article.id} to={`/journal/${article.slug}`} className="group block border-t border-line pt-6">
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
