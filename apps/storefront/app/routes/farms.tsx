import { Link } from "react-router";

import type { Route } from "./+types/farms";
import { Section } from "../components/catalogue";
import { loadFarms } from "../lib/catalogue.server";
import { seoMeta } from "../lib/seo";

export async function loader() {
  return { farms: await loadFarms() };
}

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "The farmers",
    description: "The verified farms and collectives that grow the True Grit market.",
    canonicalPath: "/farms",
    indexing: "index",
  });
}

export default function FarmsPage({ loaderData }: Route.ComponentProps) {
  return (
    <Section eyebrow="The people" heading="Farms we can vouch for">
      <div className="grid gap-6 md:grid-cols-3">
        {loaderData.farms.map((farm) => (
          <Link
            key={farm.id}
            to={`/farms/${farm.slug}`}
            className="group rounded-md border border-line bg-surface p-6 shadow-card transition-transform duration-200 hover:-translate-y-0.5"
          >
            <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
              Since {farm.establishedYear}
            </p>
            <h2 className="mt-2 font-display text-xl text-ink group-hover:text-brand">{farm.name}</h2>
            <p className="mt-1 text-sm text-ink-muted">
              {farm.farmerName} · {farm.region}
            </p>
            <p className="mt-3 text-sm text-ink">{farm.summary}</p>
            <p className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-subtle px-3 py-1 text-xs font-medium text-brand">
              <span aria-hidden>✓</span> {farm.certification}
            </p>
          </Link>
        ))}
      </div>
    </Section>
  );
}
