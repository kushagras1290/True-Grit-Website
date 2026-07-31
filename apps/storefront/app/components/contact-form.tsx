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
  submitLabel = "Send message",
  successMessage = "Your message has been sent. We will reply by email.",
  compact = false,
}: ContactFormProps) {
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
        subject: String(values.get("subject") ?? ""),
        message: String(values.get("message") ?? ""),
      });
      form.reset();
      setStatus("sent");
    } catch {
      setStatus("idle");
      setError("Could not send your message. Email us directly at support@truegrit.test.");
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      {!commerceLive ? (
        <p className="rounded-sm border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
          Demo mode - set <code>VITE_API_URL</code> to send contact emails.
        </p>
      ) : null}
      {status === "sent" ? (
        <p
          role="status"
          className="rounded-sm border border-line bg-subtle px-4 py-3 text-sm text-brand"
        >
          {successMessage}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className={compact ? "space-y-4" : "grid gap-4 sm:grid-cols-2"}>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-ink-muted">Name</span>
          <input name="name" required minLength={2} className={FIELD} />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-ink-muted">Email</span>
          <input name="email" type="email" required className={FIELD} />
        </label>
      </div>
      <label className="block space-y-1">
        <span className="text-xs font-medium text-ink-muted">Subject</span>
        <input
          name="subject"
          required
          minLength={3}
          defaultValue={defaultSubject}
          className={FIELD}
        />
      </label>
      <label className="block space-y-1">
        <span className="text-xs font-medium text-ink-muted">Message</span>
        <textarea
          name="message"
          required
          minLength={10}
          rows={compact ? 4 : 7}
          placeholder={messagePlaceholder}
          className={`${FIELD} py-3`}
        />
      </label>
      <button
        type="submit"
        disabled={status === "sending"}
        className="inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:opacity-50"
      >
        {status === "sending" ? "Sending..." : submitLabel}
      </button>
    </form>
  );
}
