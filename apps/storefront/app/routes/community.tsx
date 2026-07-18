import { useEffect, useState } from "react";
import { Link } from "react-router";

import type { Route } from "./+types/community";
import { Section } from "../components/catalogue";
import { catalogueRuntime, loadRouteSeo } from "../lib/catalogue.server";
import { useCustomer } from "../lib/customer-auth";
import { listDiscussions, type DiscussionSummary } from "../lib/community";
import { mergeRouteSeo, seoMeta } from "../lib/seo";

const fallbackSeo = {
  title: "Community",
  description: "Open discussions with the True Grit community.",
  canonicalPath: "/community",
  indexing: "index",
} as const;

export async function loader({ context }: Route.LoaderArgs) {
  return { seoOverride: await loadRouteSeo("/community", catalogueRuntime(context)) };
}

export function meta({ data }: Route.MetaArgs) {
  return seoMeta(mergeRouteSeo(data?.seoOverride, fallbackSeo));
}

export default function CommunityPage(_props: Route.ComponentProps) {
  const { status } = useCustomer();
  const [discussions, setDiscussions] = useState<DiscussionSummary[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    listDiscussions()
      .then((items) => active && setDiscussions(items))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, []);

  return (
    <Section eyebrow="Community" heading="Open discussions">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-lg text-sm text-ink-muted">
          Ask questions, swap tips, and talk to other members of the True Grit community.
        </p>
        {status === "authenticated" ? (
          <Link
            to="/community/new"
            className="inline-flex min-h-11 shrink-0 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
          >
            Start a discussion
          </Link>
        ) : (
          <p className="text-xs text-ink-muted">Sign in to start a discussion or comment.</p>
        )}
      </div>

      {failed ? (
        <p className="text-sm text-ink-muted">Discussions are unavailable right now.</p>
      ) : discussions === null ? (
        <p className="text-sm text-ink-muted">Loading discussions…</p>
      ) : discussions.length === 0 ? (
        <p className="text-sm text-ink-muted">No discussions yet — be the first to start one.</p>
      ) : (
        <ul className="mx-auto max-w-2xl divide-y divide-line rounded-md border border-line bg-surface">
          {discussions.map((entry) => (
            <li key={entry.id}>
              <Link to={`/community/${entry.id}`} className="block px-5 py-4 hover:bg-canvas/60">
                <h2 className="font-display text-lg text-ink">{entry.title}</h2>
                <p className="mt-1 text-sm text-ink-muted">{entry.excerpt}</p>
                <p className="mt-2 text-xs text-ink-muted">
                  {entry.authorName} · {entry.commentCount} comment{entry.commentCount === 1 ? "" : "s"} ·{" "}
                  {new Date(entry.lastActivityAt).toLocaleDateString()}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
