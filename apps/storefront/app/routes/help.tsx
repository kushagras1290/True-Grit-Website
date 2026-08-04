import { Link } from "react-router";

import type { Route } from "./+types/help";
import { CmsPage } from "../components/cms-page";
import { Section } from "../components/catalogue";
import { CopyBlock, InfoGrid, StaticHero } from "../components/static-page";
import { loadCmsRoute } from "../lib/cms-route.server";
import { seoMeta } from "../lib/seo";
import { LocalizedText } from "../lib/i18n/localized-text";

const fallbackSeo = {
  title: "Help",
  description:
    "Quick help for True Grit orders, delivery, returns, accounts and product questions.",
  canonicalPath: "/help",
  indexing: "index",
} as const;

export async function loader({ request, context }: Route.LoaderArgs) {
  return loadCmsRoute("help", request, context);
}

export function meta({ data, matches }: Route.MetaArgs) {
  return seoMeta(data?.page?.seo ?? fallbackSeo, matches);
}

export default function HelpPage({ loaderData }: Route.ComponentProps) {
  if (loaderData.page) return <CmsPage page={loaderData.page} data={loaderData.blockData} />;
  return (
    <>
      <StaticHero
        eyebrow="Help"
        title="Fast answers for orders, delivery and product questions."
        description="Start with the common paths below. If your issue is tied to an order, include the order reference when contacting support."
      />

      <Section eyebrow="Common help paths" heading="What do you need?">
        <InfoGrid
          items={[
            {
              title: "Track a delivery",
              body: "Check delivery guidance, dispatch rhythm and missed-delivery handling.",
            },
            {
              title: "Fix an order issue",
              body: "Use the returns page for damaged, missing, incorrect or below-standard products.",
            },
            {
              title: "Ask about a product",
              body: "Send the product name and city so support can check freshness, lot and serviceability details.",
            },
          ]}
        />
        <div className="mt-6 flex flex-wrap gap-3">
          {(
            [
              ["Delivery", "/delivery"],
              ["Returns", "/returns"],
              ["Contact", "/contact"],
            ] as const
          ).map(([label, path]) => (
            <Link
              key={path}
              to={path}
              className="inline-flex min-h-11 items-center rounded-sm border border-line px-4 text-sm font-medium text-ink hover:bg-surface"
            >
              {label}
            </Link>
          ))}
        </div>
      </Section>

      <Section tone="surface">
        <div className="mx-auto max-w-3xl space-y-8">
          <CopyBlock title="Can I change an order after placing it?">
            <p>
              <LocalizedText>
                Contact support as soon as possible. Changes are usually possible before picking,
                packing or harvest allocation starts.
              </LocalizedText>
            </p>
          </CopyBlock>
          <CopyBlock title="Why is some produce unavailable in my city?">
            <p>
              <LocalizedText>
                Some fresh products only ship where the route can preserve quality within the
                promised delivery window.
              </LocalizedText>
            </p>
          </CopyBlock>
          <CopyBlock title="Where do I see farm details?">
            <p>
              <LocalizedText>
                Product pages include farm, certification, harvest and packing information. The
                Farmers page lists every current partner farm.
              </LocalizedText>
            </p>
          </CopyBlock>
        </div>
      </Section>
    </>
  );
}
