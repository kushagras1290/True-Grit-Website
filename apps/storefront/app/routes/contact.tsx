import type { Route } from "./+types/contact";
import { Section } from "../components/catalogue";
import { ContactForm } from "../components/contact-form";
import { seoMeta } from "../lib/seo";

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
          <p className="text-xs font-semibold tracking-[0.14em] uppercase opacity-80">Contact us</p>
          <h1 className="mt-3 max-w-2xl font-display text-4xl leading-tight">
            Questions about an order, farm, product or partnership?
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
