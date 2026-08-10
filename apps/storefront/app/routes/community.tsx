import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";

import type { Route } from "./+types/community";
import { Section } from "../components/catalogue";
import { PageBanner } from "../components/page-banner";
import { PageLinkPagination } from "../components/pagination";
import { catalogueRuntime, loadRouteSeo } from "../lib/catalogue.server";
import { listDiscussions, type DiscussionSummary } from "../lib/community";
import { useCustomer } from "../lib/customer-auth";
import { mediaUrl } from "../lib/media";
import { mergeRouteSeo, seoMeta } from "../lib/seo";
import { LocalizedText, useLocalizePlural } from "../lib/i18n/localized-text";
import { useDateFormatter } from "../lib/i18n/dates";
import { useLocaleContext } from "../lib/i18n/context";

const DISCUSSIONS_PAGE_SIZE = 12;
const fallbackSeo = {
  title: "Community",
  description: "Open discussions with the True Grit community.",
  canonicalPath: "/community",
  indexing: "index",
} as const;

export async function loader({ context }: Route.LoaderArgs) {
  return { seoOverride: await loadRouteSeo("/community", catalogueRuntime(context)) };
}

export function meta({ data, matches }: Route.MetaArgs) {
  return seoMeta(mergeRouteSeo(data?.seoOverride, fallbackSeo), matches);
}

export default function CommunityPage(_props: Route.ComponentProps) {
  const plural = useLocalizePlural();
  const formatDate = useDateFormatter();
  const { locale } = useLocaleContext();
  const { status } = useCustomer();
  const [searchParams] = useSearchParams();
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const [discussions, setDiscussions] = useState<DiscussionSummary[] | null>(null);
  const [total, setTotal] = useState(0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setDiscussions(null);
    setFailed(false);
    listDiscussions(locale, DISCUSSIONS_PAGE_SIZE, (page - 1) * DISCUSSIONS_PAGE_SIZE)
      .then((result) => {
        if (!active) return;
        setDiscussions(result.items);
        setTotal(result.total);
      })
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, [locale, page]);

  return (
    <>
      <PageBanner
        imageUrl="/banners/content/community-useful-conversations.webp"
        imageAlt="Community members exchanging seeds and practical food notes around a table"
        eyebrow="True Grit community"
        heading="Useful conversations, grounded in experience"
        description="Ask specific questions, compare what worked and leave enough detail for the next person to act on."
      />
      <Section eyebrow="Community" heading="Open discussions">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-lg text-sm text-ink-muted">
            <LocalizedText>
              Ask questions, swap tips, and talk to other members of the True Grit community.
            </LocalizedText>
          </p>
          {status === "authenticated" ? (
            <Link
              to="/community/new"
              className="inline-flex min-h-11 shrink-0 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
            >
              <LocalizedText>Start a discussion</LocalizedText>
            </Link>
          ) : (
            <p className="text-xs text-ink-muted">
              <LocalizedText>Sign in to start a discussion or comment.</LocalizedText>
            </p>
          )}
        </div>

        {failed ? (
          <p className="text-sm text-ink-muted">
            <LocalizedText>Discussions are unavailable right now.</LocalizedText>
          </p>
        ) : discussions === null ? (
          <p className="text-sm text-ink-muted">
            <LocalizedText>Loading discussions…</LocalizedText>
          </p>
        ) : discussions.length === 0 ? (
          <p className="text-sm text-ink-muted">
            <LocalizedText>No discussions yet. Be the first to start one.</LocalizedText>
          </p>
        ) : (
          <div>
            <p className="mb-4 text-sm text-ink-muted" role="status">
              {plural("{count} discussion", "{count} discussions", total)}
            </p>
            {/* Three across at a normal desktop width, and the count follows the
              space actually available: `auto-fill` recomputes on resize *and*
              on browser zoom, so the row reflows to 2 or 1 instead of holding a
              fixed column count and overflowing. `min(100%, …)` keeps the track
              from exceeding the container on a narrow phone. */}
            <ul className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,21rem),1fr))] gap-5">
              {discussions.map((entry) => (
                <li key={entry.id} className="flex">
                  <Link
                    to={`/community/${entry.id}`}
                    className="flex w-full flex-col overflow-hidden rounded-md border border-line bg-surface hover:bg-canvas/60"
                  >
                    {entry.imageUrl ? (
                      <img
                        src={mediaUrl(entry.imageUrl)}
                        alt={entry.imageAlt || ""}
                        className="aspect-[16/9] w-full bg-subtle object-contain"
                        loading="lazy"
                      />
                    ) : null}
                    <span className="flex flex-1 flex-col px-5 py-4">
                      <h2 className="font-display text-lg leading-snug text-ink">{entry.title}</h2>
                      <span className="mt-1 line-clamp-3 text-sm text-ink-muted">
                        {entry.excerpt}
                      </span>
                      {/* Pushed to the bottom so the meta line sits flush across a
                        row of cards whose titles differ in length. */}
                      <span className="mt-auto pt-3 text-xs text-ink-muted">
                        {entry.authorName} ·{" "}
                        {plural("{count} comment", "{count} comments", entry.commentCount)} ·{" "}
                        {formatDate(entry.lastActivityAt)}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
            <PageLinkPagination page={page} pageSize={DISCUSSIONS_PAGE_SIZE} total={total} />
          </div>
        )}
      </Section>
    </>
  );
}
