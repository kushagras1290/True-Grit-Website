import { useState, type FormEvent } from "react";
import { data, Link } from "react-router";

import type { Route } from "./+types/discussion";
import { Section } from "../components/catalogue";
import { PageBanner } from "../components/page-banner";
import { catalogueRuntime, loadDiscussion } from "../lib/catalogue.server";
import { AuthError, useCustomer } from "../lib/customer-auth";
import { createComment, getDiscussion, type DiscussionDetail } from "../lib/community";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { seoMeta } from "../lib/seo";
import { LocalizedText, useLocalizePlural, useLocalizeText } from "../lib/i18n/localized-text";
import { useDateFormatter } from "../lib/i18n/dates";
import { useLocaleContext } from "../lib/i18n/context";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const runtime = catalogueRuntime(context);
  const { locale } = resolveLocale(request);
  const discussion = await loadDiscussion(params.id, runtime, locale.code);
  if (!discussion) throw data("Discussion not found", { status: 404 });
  return { discussion };
}

export function meta({ data: loaderData, matches }: Route.MetaArgs) {
  if (!loaderData) return seoMeta(null, matches);
  return seoMeta(loaderData.discussion.seo, matches);
}

const FIELD =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

export default function DiscussionPage({ loaderData }: Route.ComponentProps) {
  const plural = useLocalizePlural();
  const localize = useLocalizeText();
  const formatDate = useDateFormatter();
  const { locale } = useLocaleContext();
  const { customer, status } = useCustomer();
  const [discussion, setDiscussion] = useState<DiscussionDetail>(loaderData.discussion);
  const [commentBody, setCommentBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    return getDiscussion(discussion.id, locale)
      .then((entry) => setDiscussion(entry))
      .catch(() => {
        // A refresh failure after posting leaves the previous (still valid)
        // discussion state on screen rather than replacing a working page
        // with a "not found" state over a transient network hiccup.
      });
  }

  async function handleComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await createComment(discussion.id, commentBody);
      setCommentBody("");
      await reload();
    } catch (caught) {
      setError(caught instanceof AuthError ? caught.message : "Could not post your comment.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageBanner
        imageUrl={discussion.imageUrl || "/banners/content/community-useful-conversations.webp"}
        imageAlt={discussion.imageAlt || discussion.title}
        eyebrow="Community discussion"
        heading={discussion.title}
        description={`${discussion.authorName} - ${formatDate(discussion.createdAt)}`}
      />
      <Section>
        <div className="mx-auto max-w-2xl space-y-8">
          <p className="whitespace-pre-wrap text-sm text-ink">{discussion.body}</p>

          <div>
            <h2 className="mb-3 font-display text-lg text-ink">
              {plural("{count} comment", "{count} comments", discussion.comments.length)}
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
                      {comment.authorName} · {formatDate(comment.createdAt)}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{comment.body}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {status === "authenticated" && customer ? (
            <form className="space-y-3 border-t border-line pt-6" onSubmit={handleComment}>
              {error ? <p className="text-sm text-danger">{localize(error)}</p> : null}
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
                {submitting ? (
                  <LocalizedText>{"Posting..."}</LocalizedText>
                ) : (
                  <LocalizedText>{"Post comment"}</LocalizedText>
                )}
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
