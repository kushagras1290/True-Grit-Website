import type { Route } from "./+types/returns";
import { CmsPage } from "../components/cms-page";
import { Section } from "../components/catalogue";
import { InfoGrid, PolicyList, StaticHero, SupportCta } from "../components/static-page";
import { loadCmsRoute } from "../lib/cms-route.server";
import { seoMeta } from "../lib/seo";

const fallbackSeo = {
  title: "Returns and refunds",
  description: "True Grit returns, replacement and refund policy for fresh and pantry orders.",
  canonicalPath: "/returns",
  indexing: "index",
} as const;

export async function loader({ request, context }: Route.LoaderArgs) {
  return loadCmsRoute("returns", request, context);
}

export function meta({ data, matches }: Route.MetaArgs) {
  return seoMeta(data?.page?.seo ?? fallbackSeo, matches);
}

export default function ReturnsPage({ loaderData }: Route.ComponentProps) {
  if (loaderData.page) return <CmsPage page={loaderData.page} data={loaderData.blockData} />;
  return (
    <>
      <StaticHero
        eyebrow="Returns"
        title="If the food arrives wrong, damaged or below standard, we make it right."
        description="Fresh food is time-sensitive, so returns are handled through photos, batch details and a quick support review instead of asking you to ship produce back."
      />

      <Section eyebrow="Resolution options" heading="What support can do">
        <InfoGrid
          items={[
            {
              title: "Replacement",
              body: "Available when a product arrives damaged, missing, incorrect or visibly below the published quality standard.",
            },
            {
              title: "Refund",
              body: "Issued to the original payment method when replacement is not practical or the product is unavailable.",
            },
            {
              title: "Store credit",
              body: "Offered when you prefer to apply the resolution to the next seasonal drop.",
            },
          ]}
        />
      </Section>

      <Section tone="surface">
        <PolicyList
          items={[
            {
              title: "Fresh produce window",
              body: "Report fresh produce issues within 24 hours of delivery with clear photos of the product, label and outer packaging.",
            },
            {
              title: "Pantry goods window",
              body: "Report sealed pantry goods issues within 7 days of delivery. Keep the product and packaging until support confirms the resolution.",
            },
            {
              title: "Not eligible",
              body: "We cannot replace products damaged after delivery, products stored against guidance, or fresh produce reported after the quality window.",
            },
          ]}
        />
      </Section>

      <SupportCta text="For return help, include the order reference, product name, delivery date and photos." />
    </>
  );
}
