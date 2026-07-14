import { useState, type FormEvent } from "react";

import type { Route } from "./+types/contact";
import { Section } from "../components/catalogue";
import { commerceLive, sendContactMessage } from "../lib/commerce";
import { seoMeta } from "../lib/seo";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Contact us",
    description: "Contact True Grit support by email for orders, farms, products and partnerships.",
    canonicalPath: "/contact",
    indexing: "index",
  });
}

const FIELD =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

export default function ContactPage(_props: Route.ComponentProps) {
  const [status, setStatus] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setStatus("sending");
    setError(null);
    try {
      await sendContactMessage({
        name: String(form.get("name") ?? ""),
        email: String(form.get("email") ?? ""),
        subject: String(form.get("subject") ?? ""),
        message: String(form.get("message") ?? ""),
      });
      event.currentTarget.reset();
      setStatus("sent");
    } catch {
      setStatus("idle");
      setError("Could not send your message. Email us directly at support@truegrit.test.");
    }
  }

  return (
    <>
      <header className="bg-brand text-ink-inverse">
        <div className="mx-auto max-w-[80rem] px-4 py-16 sm:px-6">
          <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-80">
            Contact us
          </p>
          <h1 className="mt-3 max-w-2xl font-display text-4xl leading-tight">
            Questions about an order, farm, product or partnership?
          </h1>
        </div>
      </header>
      <Section>
        <div className="grid gap-10 lg:grid-cols-[1fr_360px]">
          <form className="max-w-2xl space-y-4" onSubmit={handleSubmit}>
            {!commerceLive ? (
              <p className="rounded-sm border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
                Demo mode - set <code>VITE_API_URL</code> to send contact emails.
              </p>
            ) : null}
            {status === "sent" ? (
              <p className="rounded-sm border border-line bg-subtle px-4 py-3 text-sm text-brand">
                Your message has been sent. We will reply by email.
              </p>
            ) : null}
            {error ? <p className="text-sm text-danger">{error}</p> : null}
            <label className="block space-y-1">
              <span className="text-xs font-medium text-ink-muted">Name</span>
              <input name="name" required minLength={2} className={FIELD} />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium text-ink-muted">Email</span>
              <input name="email" type="email" required className={FIELD} />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium text-ink-muted">Subject</span>
              <input name="subject" required minLength={3} className={FIELD} />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium text-ink-muted">Message</span>
              <textarea
                name="message"
                required
                minLength={10}
                rows={7}
                className={`${FIELD} py-3`}
              />
            </label>
            <button
              type="submit"
              disabled={status === "sending"}
              className="inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:opacity-50"
            >
              {status === "sending" ? "Sending..." : "Send message"}
            </button>
          </form>
          <aside className="space-y-5">
            <div>
              <h2 className="font-display text-xl text-ink">Email</h2>
              <a
                href="mailto:support@truegrit.test"
                className="mt-2 block text-sm text-brand underline-offset-4 hover:underline"
              >
                support@truegrit.test
              </a>
            </div>
            <div>
              <h2 className="font-display text-xl text-ink">What to include</h2>
              <p className="mt-2 text-sm text-ink-muted">
                For order help, include your order reference. For farm or product questions, include
                the product name and city.
              </p>
            </div>
          </aside>
        </div>
      </Section>
    </>
  );
}
