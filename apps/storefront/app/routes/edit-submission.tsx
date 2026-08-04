import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import type { Route } from "./+types/edit-submission";
import { Section } from "../components/catalogue";
import { SubmissionForm } from "../components/submission-form";
import { useCustomer } from "../lib/customer-auth";
import { getMySubmission, type SubmissionDetail } from "../lib/submissions";
import { seoMeta } from "../lib/seo";
import { LocalizedText } from "../lib/i18n/localized-text";

export function meta({ matches }: Route.MetaArgs) {
  return seoMeta(
    {
      title: "Edit your submission",
      description: "Revise a blog post or recipe submission after requested changes.",
      canonicalPath: "/account/submissions",
      indexing: "noindex",
    },
    matches,
  );
}

export default function EditSubmissionPage(_props: Route.ComponentProps) {
  const { id = "" } = useParams();
  const { customer, status } = useCustomer();
  const [submission, setSubmission] = useState<SubmissionDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [resubmitted, setResubmitted] = useState(false);

  useEffect(() => {
    if (status !== "authenticated") return;
    let active = true;
    getMySubmission(id)
      .then((entry) => active && setSubmission(entry))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, [id, status]);

  if (status === "loading") {
    return (
      <Section eyebrow="Edit submission" heading="Loading...">
        <p className="text-sm text-ink-muted">
          <LocalizedText>One moment…</LocalizedText>
        </p>
      </Section>
    );
  }

  if (status === "anonymous" || customer === null) {
    return (
      <Section eyebrow="Edit submission" heading="You're signed out">
        <p className="max-w-md text-sm text-ink-muted">
          <LocalizedText>Sign in to edit your submission.</LocalizedText>
        </p>
      </Section>
    );
  }

  if (resubmitted) {
    return (
      <Section eyebrow="Edit submission" heading="Sent back for another look">
        <p className="max-w-md text-sm text-ink-muted">
          <LocalizedText>Thanks — your revised submission is back with our editors.</LocalizedText>
        </p>
        <Link
          to="/account/submissions"
          className="mt-5 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
        >
          <LocalizedText>View my submissions</LocalizedText>
        </Link>
      </Section>
    );
  }

  if (failed) {
    return (
      <Section eyebrow="Edit submission" heading="Submission not found">
        <Link
          to="/account/submissions"
          className="inline-flex min-h-11 items-center rounded-sm border border-line px-5 text-sm font-medium text-ink hover:bg-canvas"
        >
          <LocalizedText>Back to my submissions</LocalizedText>
        </Link>
      </Section>
    );
  }

  if (submission === null) {
    return (
      <Section eyebrow="Edit submission" heading="Loading...">
        <p className="text-sm text-ink-muted">
          <LocalizedText>One moment…</LocalizedText>
        </p>
      </Section>
    );
  }

  if (submission.status !== "changes_requested") {
    return (
      <Section eyebrow="Edit submission" heading="Nothing to edit right now">
        <p className="max-w-md text-sm text-ink-muted">
          <LocalizedText>
            This submission can only be edited while it has requested changes.
          </LocalizedText>
        </p>
        <Link
          to="/account/submissions"
          className="mt-5 inline-flex min-h-11 items-center rounded-sm border border-line px-5 text-sm font-medium text-ink hover:bg-canvas"
        >
          <LocalizedText>Back to my submissions</LocalizedText>
        </Link>
      </Section>
    );
  }

  return (
    <Section
      eyebrow="Edit submission"
      heading={submission.contentType === "article" ? "Revise your post" : "Revise your recipe"}
    >
      {submission.reviewerNotes ? (
        <div className="mb-6 max-w-2xl rounded-sm border border-line bg-canvas px-4 py-3 text-sm text-ink">
          <p className="font-medium">
            <LocalizedText>Editor's note</LocalizedText>
          </p>
          <p className="mt-1 text-ink-muted">{submission.reviewerNotes}</p>
        </div>
      ) : null}
      <SubmissionForm
        contentType={submission.contentType}
        submissionId={submission.id}
        initial={submission}
        onSuccess={() => setResubmitted(true)}
      />
    </Section>
  );
}
