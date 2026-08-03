import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import type { Route } from "./+types/new-discussion";
import { Section } from "../components/catalogue";
import { useCustomer, AuthError } from "../lib/customer-auth";
import { createDiscussion } from "../lib/community";
import { seoMeta } from "../lib/seo";
import { LocalizedText } from "../lib/i18n/localized-text";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Start a discussion",
    description: "Start a new discussion with the True Grit community.",
    canonicalPath: "/community/new",
    indexing: "noindex",
  });
}

const FIELD =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

export default function NewDiscussionPage(_props: Route.ComponentProps) {
  const { customer, status } = useCustomer();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (status === "loading") {
    return (
      <Section eyebrow="Community" heading="Loading...">
        <p className="text-sm text-ink-muted">
          <LocalizedText>One moment…</LocalizedText>
        </p>
      </Section>
    );
  }

  if (status === "anonymous" || customer === null) {
    return (
      <Section eyebrow="Community" heading="Sign in to start a discussion">
        <p className="max-w-md text-sm text-ink-muted">
          <LocalizedText>
            Open the account menu to sign in, then come back here to start a discussion.
          </LocalizedText>
        </p>
        <Link
          to="/community"
          className="mt-5 inline-flex min-h-11 items-center rounded-sm border border-line px-5 text-sm font-medium text-ink hover:bg-canvas"
        >
          <LocalizedText>Back to community</LocalizedText>
        </Link>
      </Section>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    setSubmitting(true);
    try {
      const result = await createDiscussion({
        title: String(form.get("title") ?? ""),
        body: String(form.get("body") ?? ""),
      });
      void navigate(`/community/${result.id}`);
    } catch (caught) {
      setError(caught instanceof AuthError ? caught.message : "Could not start the discussion.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Section eyebrow="Community" heading="Start a discussion">
      <form className="max-w-2xl space-y-4" onSubmit={handleSubmit}>
        {error ? <p className="text-sm text-danger">{error}</p> : null}
        <label className="block space-y-1">
          <span className="text-xs font-medium text-ink-muted">
            <LocalizedText>Title</LocalizedText>
          </span>
          <input name="title" required minLength={5} maxLength={200} className={FIELD} />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-ink-muted">
            <LocalizedText>What's on your mind?</LocalizedText>
          </span>
          <textarea name="body" required minLength={20} rows={8} className={`${FIELD} py-3`} />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "Starting..." : "Start discussion"}
        </button>
      </form>
    </Section>
  );
}
