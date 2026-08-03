import type { Route } from "./+types/contact";
import { Section } from "../components/catalogue";
import { ContactForm } from "../components/contact-form";
import { seoMeta } from "../lib/seo";
import { LocalizedText } from "../lib/i18n/localized-text";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Contact us",
    description: "Contact True Grit support by email for orders, farms, products and partnerships.",
    canonicalPath: "/contact",
    indexing: "index",
  });
}

export default function ContactPage(_props: Route.ComponentProps) {
  return (
    <>
      <header className="bg-brand text-ink-inverse">
        <div className="mx-auto max-w-[80rem] px-4 py-16 sm:px-6">
          <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-80">
            <LocalizedText>Contact us</LocalizedText>
          </p>
          <h1 className="mt-3 max-w-2xl font-display text-4xl leading-tight">
            <LocalizedText>Questions about an order, farm, product or partnership?</LocalizedText>
          </h1>
        </div>
      </header>
      <Section>
        <div className="grid gap-10 lg:grid-cols-[1fr_360px]">
          {/* Same form as the search page and the payments-off checkout — see
              components/contact-form.tsx. */}
          <div className="max-w-2xl">
            <ContactForm />
          </div>
          <aside className="space-y-5">
            <div>
              <h2 className="font-display text-xl text-ink">
                <LocalizedText>Email</LocalizedText>
              </h2>
              <a
                href="mailto:support@truegrit.test"
                className="mt-2 block text-sm text-brand underline-offset-4 hover:underline"
              >
                <LocalizedText>support@truegrit.test</LocalizedText>
              </a>
            </div>
            <div>
              <h2 className="font-display text-xl text-ink">
                <LocalizedText>What to include</LocalizedText>
              </h2>
              <p className="mt-2 text-sm text-ink-muted">
                <LocalizedText>
                  For order help, include your order reference. For farm or product questions,
                  include the product name and city.
                </LocalizedText>
              </p>
            </div>
          </aside>
        </div>
      </Section>

      {/* A second, separate submission rather than a "Suggestion" option
          folded into the form above: a suggestion is not a problem to solve
          (no order reference, no product to look up), and keeping it as its
          own section says that plainly rather than making a suggestion
          compete with support requests in one inbox-sorting field. Reuses
          `ContactForm` end to end -- same `/v1/public/contact` submission,
          same email delivery -- only `defaultSubject` differs, the same
          pattern already used for the payments-off checkout fallback and the
          product interest form (product.tsx). The heading/intro below are
          plain English on purpose, like `LanguageSuggestionPrompt`: they are
          new copy with no translated catalogue entry yet, and shipping them
          untranslated in every language beats blocking this section on a
          fifty-language translation pass. The form's own fields (name,
          email, subject, message...) are unaffected -- those already come
          from the translated `contact.*` catalogue via `ContactForm`. */}
      <Section tone="subtle" eyebrow="Suggestions" heading="Have a suggestion?">
        <div className="max-w-2xl">
          <p className="-mt-4 mb-6 text-sm text-ink-muted">
            <LocalizedText>
              A product you would like us to carry, a feature you wish the site had, or anything
              else that would make True Grit better — we read every one of these ourselves.
            </LocalizedText>
          </p>
          <ContactForm
            compact
            defaultSubject="Suggestion"
            messagePlaceholder="What would you like to see?"
            successMessage="Thanks — your suggestion has been sent."
            submitLabel="Send suggestion"
          />
        </div>
      </Section>
    </>
  );
}
