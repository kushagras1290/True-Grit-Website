import { useState } from "react";
import { Link } from "react-router";

import type { Route } from "./+types/submit-recipe";
import { Section } from "../components/catalogue";
import { SubmissionForm } from "../components/submission-form";
import { catalogueRuntime, loadRouteSeo } from "../lib/catalogue.server";
import { useCustomer } from "../lib/customer-auth";
import { mergeRouteSeo, seoMeta } from "../lib/seo";

const fallbackSeo = {
  title: "Post a recipe",
  description: "Share a recipe with the True Grit community.",
  canonicalPath: "/recipes/submit",
  indexing: "noindex",
} as const;

export async function loader({ context }: Route.LoaderArgs) {
  return { seoOverride: await loadRouteSeo("/recipes/submit", catalogueRuntime(context)) };
}

export function meta({ data }: Route.MetaArgs) {
  return seoMeta(mergeRouteSeo(data?.seoOverride, fallbackSeo));
}

export default function SubmitRecipePage(_props: Route.ComponentProps) {
  const { customer, status } = useCustomer();
  const [submitted, setSubmitted] = useState(false);

  if (status === "loading") {
    return (
      <Section eyebrow="Post a recipe" heading="Loading...">
        <p className="text-sm text-ink-muted">One moment…</p>
      </Section>
    );
  }

  if (status === "anonymous" || customer === null) {
    return (
      <Section eyebrow="Post a recipe" heading="Sign in to share a recipe">
        <p className="max-w-md text-sm text-ink-muted">
          Open the account menu to sign in or create an account, then come back here to submit your
          recipe.
        </p>
        <Link
          to="/recipes"
          className="mt-5 inline-flex min-h-11 items-center rounded-sm border border-line px-5 text-sm font-medium text-ink hover:bg-canvas"
        >
          Back to recipes
        </Link>
      </Section>
    );
  }

  if (submitted) {
    return (
      <Section eyebrow="Post a recipe" heading="Thanks for sharing!">
        <p className="max-w-md text-sm text-ink-muted">
          Your recipe is with our editors. We will email you at your contact address once it is
          approved, or if we need changes first.
        </p>
        <div className="mt-5 flex gap-3">
          <Link
            to="/account/submissions"
            className="inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
          >
            View my submissions
          </Link>
          <Link
            to="/recipes"
            className="inline-flex min-h-11 items-center rounded-sm border border-line px-5 text-sm font-medium text-ink hover:bg-canvas"
          >
            Back to recipes
          </Link>
        </div>
      </Section>
    );
  }

  return (
    <Section eyebrow="Post a recipe" heading="Share a recipe with the community">
      <p className="mb-6 max-w-2xl text-sm text-ink-muted">
        Ingredients, steps, prep and cook time — our editors review every recipe before it goes
        live.
      </p>
      <SubmissionForm
        contentType="recipe"
        defaultContactName={customer.displayName}
        defaultContactEmail={customer.email ?? undefined}
        defaultContactPhone={customer.phone ?? undefined}
        onSuccess={() => setSubmitted(true)}
      />
    </Section>
  );
}
