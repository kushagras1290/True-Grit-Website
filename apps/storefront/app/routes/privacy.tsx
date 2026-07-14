import type { Route } from "./+types/privacy";
import { Section } from "../components/catalogue";
import { PolicyList, StaticHero, SupportCta } from "../components/static-page";
import { seoMeta } from "../lib/seo";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Privacy policy",
    description: "How True Grit collects, uses and protects customer account and order data.",
    canonicalPath: "/privacy",
    indexing: "index",
  });
}

const PRIVACY_ITEMS = [
  {
    title: "Information we collect",
    body: "We collect account details, delivery details, order history, payment status, contact messages and basic site diagnostics needed to run the market.",
  },
  {
    title: "How we use it",
    body: "We use this information to process orders, support customers, prevent misuse, improve catalogue availability and communicate service updates.",
  },
  {
    title: "Payments",
    body: "Payment details are handled by the configured payment provider. True Grit stores payment status and references, not full card numbers.",
  },
  {
    title: "Cookies and sessions",
    body: "We use essential cookies for account sessions, cart continuity and security. Optional analytics should only be enabled where the deployment has consent controls.",
  },
  {
    title: "Retention",
    body: "Order and audit records are kept for operational, tax and safety reasons. Contact messages and inactive account data are reviewed periodically.",
  },
  {
    title: "Your choices",
    body: "You can ask support for access, correction or deletion of personal data where the request does not conflict with legal or fraud-prevention obligations.",
  },
];

export default function PrivacyPage(_props: Route.ComponentProps) {
  return (
    <>
      <StaticHero
        eyebrow="Privacy"
        title="Customer data is used to run the market, not to obscure it."
        description="This page explains the practical data we collect for orders, accounts, delivery and support."
      />
      <Section>
        <PolicyList items={PRIVACY_ITEMS} />
      </Section>
      <SupportCta
        heading="Privacy request?"
        text="Use the contact form and include the email address tied to your account or order."
      />
    </>
  );
}
