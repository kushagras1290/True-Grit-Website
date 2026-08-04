import type { Route } from "./+types/terms";
import { CmsPage } from "../components/cms-page";
import { Section } from "../components/catalogue";
import { PolicyList, StaticHero, SupportCta } from "../components/static-page";
import { loadCmsRoute } from "../lib/cms-route.server";
import { seoMeta } from "../lib/seo";

const fallbackSeo = {
  title: "Terms of service",
  description: "Terms for using the True Grit organic food market and placing orders.",
  canonicalPath: "/terms",
  indexing: "index",
} as const;

export async function loader({ request, context }: Route.LoaderArgs) {
  return loadCmsRoute("terms", request, context);
}

export function meta({ data, matches }: Route.MetaArgs) {
  return seoMeta(data?.page?.seo ?? fallbackSeo, matches);
}

const TERMS_ITEMS = [
  {
    title: "Using the market",
    body: "You agree to provide accurate account, delivery and contact information, and to use the site only for lawful personal or business purchases.",
  },
  {
    title: "Product availability",
    body: "Fresh and small-batch products can sell out or change with harvest conditions. If a confirmed order cannot be fulfilled, support will offer a replacement, refund or credit.",
  },
  {
    title: "Prices and taxes",
    body: "Prices are shown in Indian rupees unless stated otherwise. Final taxes, delivery charges and discounts are confirmed during checkout.",
  },
  {
    title: "Delivery and risk",
    body: "We are responsible for packing and dispatching orders to the published standard. After delivery, storage and handling become the customer's responsibility.",
  },
  {
    title: "Content and claims",
    body: "Farm stories, certification references and traceability details are published for customer transparency. Do not copy site content or brand assets without permission.",
  },
  {
    title: "Changes",
    body: "These terms may change as services, payment flows or delivery coverage evolve. The current page applies when you use the site or place an order.",
  },
];

export default function TermsPage({ loaderData }: Route.ComponentProps) {
  if (loaderData.page) return <CmsPage page={loaderData.page} data={loaderData.blockData} />;
  return (
    <>
      <StaticHero
        eyebrow="Terms"
        title="The basic rules for buying from True Grit."
        description="These terms cover orders, availability, delivery, support and responsible use of the market."
      />
      <Section>
        <PolicyList items={TERMS_ITEMS} />
      </Section>
      <SupportCta text="Questions about an order or policy are handled through support." />
    </>
  );
}
