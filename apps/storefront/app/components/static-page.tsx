import { Link } from "react-router";

import { Section } from "./catalogue";
import { LocalizedText, useLocalizeText } from "../lib/i18n/localized-text";

export function StaticHero({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  const localize = useLocalizeText();
  return (
    <header className="bg-brand text-ink-inverse">
      <div className="mx-auto max-w-[80rem] px-4 py-16 sm:px-6">
        <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-80">
          {localize(eyebrow)}
        </p>
        <h1 className="mt-3 max-w-3xl font-display text-4xl leading-tight">{localize(title)}</h1>
        <p className="mt-4 max-w-2xl text-base opacity-85">{localize(description)}</p>
      </div>
    </header>
  );
}

export function CopyBlock({ title, children }: { title: string; children: React.ReactNode }) {
  const localize = useLocalizeText();
  return (
    <section className="border-t border-line pt-5">
      <h2 className="font-display text-2xl text-ink">{localize(title)}</h2>
      <div className="mt-3 space-y-3 text-base text-ink-muted">{children}</div>
    </section>
  );
}

export function InfoGrid({
  items,
}: {
  items: Array<{ title: string; body: string; meta?: string }>;
}) {
  const localize = useLocalizeText();
  return (
    <div className="grid gap-5 md:grid-cols-3">
      {items.map((item) => (
        <article key={item.title} className="rounded-md border border-line bg-surface p-5">
          {item.meta ? (
            <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
              {localize(item.meta)}
            </p>
          ) : null}
          <h2 className="font-display text-xl text-ink">{localize(item.title)}</h2>
          <p className="mt-2 text-sm text-ink-muted">{localize(item.body)}</p>
        </article>
      ))}
    </div>
  );
}

export function PolicyList({ items }: { items: Array<{ title: string; body: string }> }) {
  const localize = useLocalizeText();
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {items.map((item) => (
        <CopyBlock key={item.title} title={item.title}>
          <p>{localize(item.body)}</p>
        </CopyBlock>
      ))}
    </div>
  );
}

export function SupportCta({
  heading = "Need a specific answer?",
  text = "Send us the order reference, product name, and delivery city so the support team can answer without back-and-forth.",
}: {
  heading?: string;
  text?: string;
}) {
  const localize = useLocalizeText();
  return (
    <Section tone="subtle">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="font-display text-2xl text-ink">{localize(heading)}</p>
          <p className="mt-1 max-w-2xl text-sm text-ink-muted">{localize(text)}</p>
        </div>
        <Link
          to="/contact"
          className="inline-flex min-h-11 w-fit items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
        >
          <LocalizedText>Contact support</LocalizedText>
        </Link>
      </div>
    </Section>
  );
}
