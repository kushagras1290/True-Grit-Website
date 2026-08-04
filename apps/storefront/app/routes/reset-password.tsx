import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import type { Route } from "./+types/reset-password";
import { Section } from "../components/catalogue";
import { AuthError, confirmPasswordReset } from "../lib/customer-auth";
import { seoMeta } from "../lib/seo";
import { LocalizedText, useLocalizeText } from "../lib/i18n/localized-text";

export function meta({ matches }: Route.MetaArgs) {
  return seoMeta(
    {
      title: "Reset password",
      description: "Set a new password for your account.",
      canonicalPath: "/reset-password",
      indexing: "noindex",
    },
    matches,
  );
}

const FIELD =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

export default function ResetPasswordPage(_props: Route.ComponentProps) {
  const localize = useLocalizeText();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!token) {
    return (
      <Section eyebrow="Reset password" heading="This link is invalid">
        <p className="text-sm text-ink-muted">
          <LocalizedText>The reset link is missing its token.</LocalizedText>
        </p>
      </Section>
    );
  }

  if (done) {
    return (
      <Section eyebrow="Reset password" heading="Password updated">
        <p className="max-w-md text-sm text-ink-muted">
          <LocalizedText>
            You can now sign in with your new password from the account menu in the header.
          </LocalizedText>
        </p>
        <Link
          to="/"
          className="mt-5 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
        >
          <LocalizedText>Back to the market</LocalizedText>
        </Link>
      </Section>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const password = String(new FormData(event.currentTarget).get("password") ?? "");
    setError(null);
    setPending(true);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
    } catch (caught) {
      setError(caught instanceof AuthError ? caught.message : "Could not reset your password.");
    } finally {
      setPending(false);
    }
  }

  return (
    <Section eyebrow="Reset password" heading="Set a new password">
      <form className="max-w-sm space-y-4" onSubmit={handleSubmit}>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-ink-muted">
            <LocalizedText>New password</LocalizedText>
          </span>
          <input
            name="password"
            type="password"
            minLength={10}
            autoComplete="new-password"
            required
            className={FIELD}
            placeholder={localize("At least 10 characters")}
          />
        </label>
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {localize(error)}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={pending}
          className="min-h-11 w-full rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-95 disabled:opacity-60"
        >
          {pending ? (
            <LocalizedText>{"Saving…"}</LocalizedText>
          ) : (
            <LocalizedText>{"Reset password"}</LocalizedText>
          )}
        </button>
      </form>
    </Section>
  );
}
