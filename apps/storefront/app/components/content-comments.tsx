/**
 * The comment thread under a blog post or a recipe.
 *
 * Identical on both, which is the reason it is one component: a reader who has
 * commented on an article should not have to relearn the control on a recipe.
 *
 * Fetched on the client, after paint. The article itself is cacheable, mostly
 * static content; the conversation under it is not, and loading the two
 * together would drag the post's time-to-first-byte down to whatever the
 * comment query costs on every single view.
 */

import { useCallback, useEffect, useState, type FormEvent } from "react";

import { useCustomer } from "../lib/customer-auth";
import {
  listContentComments,
  postContentComment,
  type CommentContentType,
  type ContentComment,
} from "../lib/content-comments";
import { useLocaleContext } from "../lib/i18n/context";

const MAX_COMMENT_LENGTH = 4000;

export function ContentComments({
  contentType,
  slug,
}: {
  contentType: CommentContentType;
  slug: string;
}) {
  const { t, locale } = useLocaleContext();
  const { customer } = useCustomer();
  const [comments, setComments] = useState<ContentComment[] | null>(null);
  const [enabled, setEnabled] = useState(true);
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [body, setBody] = useState("");

  const load = useCallback(async () => {
    try {
      const thread = await listContentComments(contentType, slug);
      setComments(thread.items);
      setEnabled(thread.enabled);
    } catch {
      // A thread that cannot be fetched is rendered as an empty one rather than
      // an error: the post is the point of the page, and a failing comment
      // widget must not make it look broken.
      setComments([]);
    }
  }, [contentType, slug]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    setPosting(true);
    setError(null);
    try {
      await postContentComment(contentType, slug, trimmed);
      setBody("");
      // Refetch rather than append locally: the server assigns the id, the
      // timestamp and the display name, and guessing any of them here would
      // show the reader something subtly different from what everyone else sees.
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("comments.failed"));
    } finally {
      setPosting(false);
    }
  }

  const heading =
    comments && comments.length > 0
      ? t("comments.headingWithCount", { count: comments.length })
      : t("comments.heading");

  return (
    <section aria-labelledby="comments-heading" className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
      <h2 id="comments-heading" className="font-display text-2xl text-ink">
        {heading}
      </h2>

      {comments === null ? (
        <p className="mt-4 text-sm text-ink-muted">{t("comments.loading")}</p>
      ) : comments.length === 0 ? (
        <p className="mt-4 text-sm text-ink-muted">{t("comments.none")}</p>
      ) : (
        <ul className="mt-6 space-y-5">
          {comments.map((comment) => (
            <li key={comment.id} className="rounded-md border border-line bg-surface p-4">
              <p className="text-xs text-ink-muted">
                {comment.authorName} ·{" "}
                {/* Formatted in the reader's language, so a Tamil visitor sees a
                    Tamil date rather than an English one. */}
                <time dateTime={comment.createdAt}>
                  {new Date(comment.createdAt).toLocaleDateString(locale)}
                </time>
              </p>
              <p className="mt-2 text-sm whitespace-pre-line text-ink">{comment.body}</p>
            </li>
          ))}
        </ul>
      )}

      {!enabled ? (
        <p className="mt-6 rounded-sm border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
          {t("comments.closed")}
        </p>
      ) : customer === null ? (
        <p className="mt-6 rounded-sm border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
          {t("comments.signInPrompt")}
        </p>
      ) : (
        <form className="mt-6 space-y-3" onSubmit={handleSubmit}>
          <label className="block space-y-1">
            <span className="sr-only">{t("comments.post")}</span>
            <textarea
              value={body}
              onChange={(event) => setBody(event.target.value)}
              rows={4}
              maxLength={MAX_COMMENT_LENGTH}
              placeholder={t("comments.placeholder")}
              className="w-full rounded-sm border border-line bg-canvas px-3 py-3 text-sm text-ink placeholder:text-ink-muted focus:border-brand focus:outline-none"
            />
          </label>
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={posting || body.trim().length === 0}
            className="inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:opacity-50"
          >
            {posting ? t("comments.posting") : t("comments.post")}
          </button>
        </form>
      )}
    </section>
  );
}
