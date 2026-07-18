import { useEffect, useState } from "react";
import { Link } from "react-router";

import type { Route } from "./+types/my-submissions";
import { Section } from "../components/catalogue";
import { useCustomer } from "../lib/customer-auth";
import { listMySubmissions, type SubmissionDetail } from "../lib/submissions";
import { seoMeta } from "../lib/seo";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Your submissions",
    description: "Track the blog posts and recipes you have submitted.",
    canonicalPath: "/account/submissions",
    indexing: "noindex",
  });
}

const STATUS_LABELS: Record<string, string> = {
  submitted: "Submitted",
  under_review: "Under review",
  changes_requested: "Changes requested",
  approved: "Approved",
  rejected: "Not published",
};

function SubmissionsList() {
  const [submissions, setSubmissions] = useState<SubmissionDetail[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    listMySubmissions()
      .then((items) => active && setSubmissions(items))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, []);

  if (failed) {
    return <p className="text-sm text-ink-muted">Your submissions are unavailable right now.</p>;
  }
  if (submissions === null) {
    return <p className="text-sm text-ink-muted">Loading your submissions…</p>;
  }
  if (submissions.length === 0) {
    return (
      <p className="text-sm text-ink-muted">
        No submissions yet.{" "}
        <Link to="/blog/submit" className="text-brand underline-offset-4 hover:underline">
          Pitch a blog post
        </Link>{" "}
        or{" "}
        <Link to="/recipes/submit" className="text-brand underline-offset-4 hover:underline">
          share a recipe
        </Link>
        .
      </p>
    );
  }

  return (
    <ul className="divide-y divide-line rounded-md border border-line bg-surface">
      {submissions.map((entry) => (
        <li key={entry.id} className="flex items-center justify-between gap-3 px-5 py-4">
          <div className="min-w-0">
            <p className="font-medium text-ink">{entry.title}</p>
            <p className="mt-0.5 text-xs text-ink-muted">
              {entry.contentType === "article" ? "Blog post" : "Recipe"} ·{" "}
              {new Date(entry.createdAt).toLocaleDateString()}
            </p>
            {entry.reviewerNotes ? (
              <p className="mt-1 text-xs text-ink-muted">Note: {entry.reviewerNotes}</p>
            ) : null}
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center rounded-sm bg-canvas px-2 py-1 text-[11px] font-medium text-ink">
              {STATUS_LABELS[entry.status] ?? entry.status}
            </span>
            {entry.status === "changes_requested" ? (
              <Link
                to={`/account/submissions/${entry.id}/edit`}
                className="text-xs font-medium text-brand hover:underline"
              >
                Edit &amp; resubmit
              </Link>
            ) : null}
            {entry.status === "approved" && entry.publishedArticleId ? (
              <Link to="/blog" className="text-xs font-medium text-brand hover:underline">
                View live
              </Link>
            ) : null}
            {entry.status === "approved" && entry.publishedRecipeId ? (
              <Link to="/recipes" className="text-xs font-medium text-brand hover:underline">
                View live
              </Link>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function MySubmissionsPage(_props: Route.ComponentProps) {
  const { customer, status } = useCustomer();

  if (status === "loading") {
    return (
      <Section eyebrow="Your submissions" heading="Loading...">
        <p className="text-sm text-ink-muted">One moment…</p>
      </Section>
    );
  }

  if (status === "anonymous" || customer === null) {
    return (
      <Section eyebrow="Your submissions" heading="You're signed out">
        <p className="max-w-md text-sm text-ink-muted">
          Sign in to see the blog posts and recipes you have submitted.
        </p>
      </Section>
    );
  }

  return (
    <Section eyebrow="Your submissions" heading="Blog posts and recipes you've pitched">
      <SubmissionsList />
    </Section>
  );
}
