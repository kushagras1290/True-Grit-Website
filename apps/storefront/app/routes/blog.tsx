import { Link } from "react-router";

import type { Route } from "./+types/blog";
import { Section } from "../components/catalogue";
import { PageBanner } from "../components/page-banner";
import { PageLinkPagination } from "../components/pagination";
import { catalogueRuntime, loadArticles } from "../lib/catalogue.server";
import { mediaUrl } from "../lib/media";
import { seoMeta } from "../lib/seo";
import { useSiteSettings } from "../lib/site-settings";

// 12 divides evenly into the 1/2/3-column breakpoints below, so the last row of
// a full page is never a lone card.
const BLOG_PAGE_SIZE = 12;

// Ships with the storefront, so the banner has an image before an owner sets
// one. Same asset the homepage hero falls back to.
const FALLBACK_BANNER_IMAGE = "/homepage-hero.png";

export async function loader({ context, request }: Route.LoaderArgs) {
  const page = Math.max(1, Number(new URL(request.url).searchParams.get("page")) || 1);
  return {
    page,
    pageSize: BLOG_PAGE_SIZE,
    articles: await loadArticles(page, BLOG_PAGE_SIZE, catalogueRuntime(context)),
  };
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
  const { banners } = useSiteSettings();

  return (
    <>
      <PageBanner
        imageUrl={banners.blogImageUrl || FALLBACK_BANNER_IMAGE}
        imageAlt={banners.blogImageAlt}
        eyebrow="The blog"
        heading="Stories worth chewing on"
        description="Notes from the field, the kitchen and everywhere in between."
      />

      <Section>
        <div className="mb-8 flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-lg text-sm text-ink-muted">
            Have a story to tell? Pitch a post and our editors will review it.
          </p>
          <Link
            to="/blog/submit"
            className="inline-flex min-h-11 shrink-0 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
          >
            Post a blog
          </Link>
        </div>

        <p className="mb-5 text-sm text-ink-muted" role="status">
          {loaderData.articles.total} stor{loaderData.articles.total === 1 ? "y" : "ies"}
        </p>

        {/* Two across at a normal desktop width, and the count follows the space
            it is actually given: `auto-fill` recomputes on resize *and* on
            browser zoom, so no breakpoint has to be maintained by hand. */}
        <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,28rem),1fr))] gap-x-8 gap-y-10">
          {loaderData.articles.items.map((article) => (
            <article key={article.id} className="flex flex-col">
              <Link to={`/blog/${article.slug}`} className="group flex flex-col">
                {article.heroImageUrl ? (
                  <img
                    src={mediaUrl(article.heroImageUrl)}
                    alt={article.heroImageAlt || ""}
                    loading="lazy"
                    className="aspect-[16/9] w-full rounded-md object-cover"
                  />
                ) : (
                  <span aria-hidden className="aspect-[16/9] w-full rounded-md bg-subtle" />
                )}
                <p className="mt-4 text-xs text-ink-muted">
                  {article.authorName} · {article.readingMinutes} min read
                </p>
                <h2 className="mt-1.5 font-display text-2xl leading-snug text-ink group-hover:text-brand">
                  {article.title}
                </h2>
                <p className="mt-2 text-base text-ink-muted">{article.excerpt}</p>
              </Link>
            </article>
          ))}
        </div>

        <PageLinkPagination
          page={loaderData.page}
          pageSize={loaderData.pageSize}
          total={loaderData.articles.total}
        />
      </Section>
    </>
  );
}
