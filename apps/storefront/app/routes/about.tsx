import { Link } from "react-router";

import type { Route } from "./+types/about";
import { Section } from "../components/catalogue";
import { CopyBlock, InfoGrid, StaticHero } from "../components/static-page";
import { seoMeta } from "../lib/seo";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "About True Grit",
    description:
      "True Grit is a traceable organic market built around verified farms, seasonal harvests and honest food.",
    canonicalPath: "/about",
    indexing: "index",
  });
}

export default function AboutPage(_props: Route.ComponentProps) {
  return (
    <>
      <StaticHero
        eyebrow="About"
        title="A market for food with a known origin."
        description="True Grit connects households with certified organic farms, small-batch processors and seasonal harvests that can be traced from source to delivery."
      />

      <Section>
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="space-y-8">
            <CopyBlock title="Why we exist">
              <p>
                Organic food should not depend on vague claims. Every product in the market is tied
                to a verified farm, certification record, harvest or processing date, and a clear
                route to the customer.
              </p>
              <p>
                We keep the catalogue intentionally small so the team can stay close to growers,
                inspect paperwork, manage freshness, and publish the context customers need before
                buying.
              </p>
            </CopyBlock>
            <CopyBlock title="How we choose partners">
              <p>
                Farms must hold a current NPOP or PGS-India certificate, agree to lot-level
                traceability, and work with seasonal availability rather than anonymous bulk supply.
                Pantry partners must press, mill or pack in small batches with dates shown plainly.
              </p>
            </CopyBlock>
          </div>

          <aside className="rounded-md border border-line bg-surface p-6">
            <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
              Built around
            </p>
            <dl className="mt-4 space-y-4">
              {[
                ["3", "verified farms and collectives"],
                ["5", "traceable market products"],
                ["2", "organic certification systems"],
              ].map(([value, label]) => (
                <div key={label}>
                  <dt className="font-display text-3xl text-brand">{value}</dt>
                  <dd className="text-sm text-ink-muted">{label}</dd>
                </div>
              ))}
            </dl>
            <Link
              to="/farms"
              className="mt-6 inline-flex min-h-11 items-center rounded-sm border border-line px-4 text-sm font-medium text-ink hover:bg-canvas"
            >
              Meet the farmers
            </Link>
          </aside>
        </div>
      </Section>

      <Section tone="subtle" eyebrow="Our operating rules" heading="What customers can expect">
        <InfoGrid
          items={[
            {
              title: "Certified first",
              body: "We verify certification before a farm or product is published in the market.",
            },
            {
              title: "Seasonal by default",
              body: "Fresh produce follows harvest calendars and ships in planned weekly cycles.",
            },
            {
              title: "Transparent support",
              body: "Order, delivery and product questions are handled through a traceable support flow.",
            },
          ]}
        />
      </Section>
    </>
  );
}
