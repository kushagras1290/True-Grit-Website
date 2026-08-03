import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";

import type { Route } from "./+types/discussion";
import { Section } from "../components/catalogue";
import { PageBanner } from "../components/page-banner";
import { AuthError, useCustomer } from "../lib/customer-auth";
import { createComment, getDiscussion, type DiscussionDetail } from "../lib/community";
import { seoMeta } from "../lib/seo";
import { LocalizedText } from "../lib/i18n/localized-text";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Discussion",
    description: "A discussion in the True Grit community.",
    canonicalPath: "/community",
    indexing: "index",
  });
}

const FIELD =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

export default function DiscussionPage(_props: Route.ComponentProps) {
  const { id = "" } = useParams();
  const { customer, status } = useCustomer();
  const [discussion, setDiscussion] = useState<DiscussionDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [commentBody, setCommentBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    return getDiscussion(id)
      .then((entry) => setDiscussion(entry))
      .catch(() => setFailed(true));
  }

  useEffect(() => {
    let active = true;
    getDiscussion(id)
      .then((entry) => active && setDiscussion(entry))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, [id]);

  async function handleComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await createComment(id, commentBody);
      setCommentBody("");
      await reload();
    } catch (caught) {
      setError(caught instanceof AuthError ? caught.message : "Could not post your comment.");
    } finally {
      setSubmitting(false);
    }
  }

  if (failed) {
    return (
      <Section eyebrow="Community" heading="Discussion not found">
        <Link
          to="/community"
          className="inline-flex min-h-11 items-center rounded-sm border border-line px-5 text-sm font-medium text-ink hover:bg-canvas"
        >
          <LocalizedText>Back to community</LocalizedText>
        </Link>
      </Section>
    );
  }

  if (discussion === null) {
    return (
      <Section eyebrow="Community" heading="Loading...">
        <p className="text-sm text-ink-muted">
          <LocalizedText>One moment…</LocalizedText>
        </p>
      </Section>
    );
  }

  return (
    <>
      <PageBanner
        imageUrl={discussion.imageUrl || "/banners/content/community-useful-conversations.webp"}
        imageAlt={discussion.imageAlt || discussion.title}
        eyebrow="Community discussion"
        heading={discussion.title}
        description={`${discussion.authorName} - ${new Date(discussion.createdAt).toLocaleDateString()}`}
      />
      <Section>
        <div className="mx-auto max-w-2xl space-y-8">
          <p className="whitespace-pre-wrap text-sm text-ink">{discussion.body}</p>

          <div>
            <h2 className="mb-3 font-display text-lg text-ink">
              {discussion.comments.length} <LocalizedText>comment</LocalizedText>
              {discussion.comments.length === 1 ? "" : "s"}
            </h2>
            {discussion.comments.length === 0 ? (
              <p className="text-sm text-ink-muted">
                <LocalizedText>No comments yet.</LocalizedText>
              </p>
            ) : (
              <ul className="space-y-4">
                {discussion.comments.map((comment) => (
                  <li key={comment.id} className="border-t border-line pt-4">
                    <p className="text-xs text-ink-muted">
                      {comment.authorName} · {new Date(comment.createdAt).toLocaleDateString()}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{comment.body}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {status === "authenticated" && customer ? (
            <form className="space-y-3 border-t border-line pt-6" onSubmit={handleComment}>
              {error ? <p className="text-sm text-danger">{error}</p> : null}
              <label className="block space-y-1">
                <span className="text-xs font-medium text-ink-muted">
                  <LocalizedText>Add a comment</LocalizedText>
                </span>
                <textarea
                  required
                  minLength={2}
                  rows={3}
                  value={commentBody}
                  onChange={(event) => setCommentBody(event.target.value)}
                  className={`${FIELD} py-2`}
                />
              </label>
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:opacity-50"
              >
                {submitting ? "Posting..." : "Post comment"}
              </button>
            </form>
          ) : (
            <p className="border-t border-line pt-6 text-sm text-ink-muted">
              <LocalizedText>Sign in to join the discussion.</LocalizedText>
            </p>
          )}
        </div>
      </Section>
    </>
  );
}
