/**
 * The contact form, in one place.
 *
 * Used on `/contact`, on the search page when a search comes up short, and on
 * checkout when the owner has switched payments off — that last case is the
 * point of extracting it: when there is no way to take an order, there still
 * has to be a way to capture the interest.
 */

import { useState, type FormEvent } from "react";

import { commerceLive, sendContactMessage } from "../lib/commerce";
import { useLocaleContext } from "../lib/i18n/context";
import { useLocalizeText } from "../lib/i18n/localized-text";

const FIELD =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

export interface ContactFormProps {
  /** Pre-fills the subject so a message from checkout or search arrives already
   *  labelled with where it came from. */
  defaultSubject?: string;
  /** Placeholder for the message box, tailored to where the form is shown. */
  messagePlaceholder?: string;
  submitLabel?: string;
  /** Shown once the message is away. */
  successMessage?: string;
  /** Stack the fields instead of using the two-up name/email row — for narrow
   *  columns such as the search-page sidebar. */
  compact?: boolean;
}

export function ContactForm({
  defaultSubject = "",
  messagePlaceholder,
  submitLabel,
  successMessage,
  compact = false,
}: ContactFormProps) {
  const { t } = useLocaleContext();
  // Callers pass these as English source text — the same contract as every
  // other prose prop in the storefront — so they are translated here rather
  // than at each of the four call sites.
  const localize = useLocalizeText();
  const [status, setStatus] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    setStatus("sending");
    setError(null);
    try {
      await sendContactMessage({
        name: String(values.get("name") ?? ""),
        email: String(values.get("email") ?? ""),
        phone: String(values.get("phone") ?? ""),
        subject: String(values.get("subject") ?? ""),
        message: String(values.get("message") ?? ""),
      });
      form.reset();
      setStatus("sent");
    } catch (caught) {
      setStatus("idle");
      // The API rejects an unringable number with a message naming the format
      // it wants, which is more use than a generic failure — show it when we
      // have one.
      setError(caught instanceof Error && caught.message ? caught.message : t("contact.failed"));
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      {!commerceLive ? (
        <p className="rounded-sm border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
          {t("common.demoMode")}
        </p>
      ) : null}
      {status === "sent" ? (
        <p
          role="status"
          className="rounded-sm border border-line bg-subtle px-4 py-3 text-sm text-brand"
        >
          {successMessage ? localize(successMessage) : t("contact.sent")}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {localize(error)}
        </p>
      ) : null}

      <div className={compact ? "space-y-4" : "grid gap-4 sm:grid-cols-2"}>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-ink-muted">{t("contact.name")}</span>
          <input name="name" required minLength={2} className={FIELD} />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-ink-muted">{t("contact.email")}</span>
          <input name="email" type="email" required className={FIELD} />
        </label>
      </div>
      {/* Required, not optional. Most of what arrives here is settled in one
          call, and a phone-only account (which the storefront lets anyone open)
          has no email address we could reply to at all. */}
      <label className="block space-y-1">
        <span className="text-xs font-medium text-ink-muted">{t("contact.phone")}</span>
        <input
          name="phone"
          type="tel"
          required
          maxLength={24}
          autoComplete="tel"
          className={FIELD}
        />
        <span className="block text-xs text-ink-muted">{t("contact.phoneHint")}</span>
      </label>
      <label className="block space-y-1">
        <span className="text-xs font-medium text-ink-muted">{t("contact.subject")}</span>
        <input
          name="subject"
          required
          minLength={3}
          defaultValue={defaultSubject ? localize(defaultSubject) : ""}
          className={FIELD}
        />
      </label>
      <label className="block space-y-1">
        <span className="text-xs font-medium text-ink-muted">{t("contact.message")}</span>
        <textarea
          name="message"
          required
          minLength={10}
          rows={compact ? 4 : 7}
          placeholder={messagePlaceholder ? localize(messagePlaceholder) : undefined}
          className={`${FIELD} py-3`}
        />
      </label>
      <button
        type="submit"
        disabled={status === "sending"}
        className="inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:opacity-50"
      >
        {status === "sending"
          ? t("contact.sending")
          : submitLabel
            ? localize(submitLabel)
            : t("contact.send")}
      </button>
    </form>
  );
}
