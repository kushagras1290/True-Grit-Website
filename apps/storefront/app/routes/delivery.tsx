import type { Route } from "./+types/delivery";
import { Section } from "../components/catalogue";
import { InfoGrid, PolicyList, StaticHero, SupportCta } from "../components/static-page";
import { seoMeta } from "../lib/seo";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Delivery",
    description: "How True Grit packs, dispatches and delivers seasonal organic food orders.",
    canonicalPath: "/delivery",
    indexing: "index",
  });
}

export default function DeliveryPage(_props: Route.ComponentProps) {
  return (
    <>
      <StaticHero
        eyebrow="Delivery"
        title="Harvest-led delivery, planned around freshness."
        description="Fresh produce ships on fixed dispatch days. Pantry goods usually leave the fulfilment centre within two working days, with cold-chain handling where needed."
      />

      <Section eyebrow="Dispatch rhythm" heading="How orders move">
        <InfoGrid
          items={[
            {
              meta: "Fresh fruit",
              title: "Tuesday orchard dispatch",
              body: "Seasonal fruit is harvested against confirmed orders and packed for Tuesday dispatch where the route supports it.",
            },
            {
              meta: "Leafy produce",
              title: "Morning harvest windows",
              body: "Greens are cut early, chilled quickly and prioritised for short-route delivery slots.",
            },
            {
              meta: "Pantry",
              title: "Two working days",
              body: "Flours, pulses and oils ship from current lots with milling, pressing or harvest dates visible on the pack.",
            },
          ]}
        />
      </Section>

      <Section tone="surface">
        <PolicyList
          items={[
            {
              title: "Delivery areas",
              body: "Serviceability is checked during checkout. Some fresh products are limited to routes that can preserve quality within the promised delivery window.",
            },
            {
              title: "Packing standards",
              body: "Orders are packed by product type: ventilated crates for fruit, chilled handling for delicate greens, and protective sleeves for glass bottles.",
            },
            {
              title: "Missed deliveries",
              body: "If a delivery cannot be completed, support will contact you with the next available attempt or a practical resolution based on the product condition.",
            },
          ]}
        />
      </Section>

      <SupportCta text="For delivery help, include your order reference, phone number and delivery city." />
    </>
  );
}
