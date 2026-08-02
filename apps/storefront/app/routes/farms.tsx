import { Link } from "react-router";

import type { Route } from "./+types/farms";
import { Section } from "../components/catalogue";
import { PageBanner } from "../components/page-banner";
import { catalogueRuntime, loadFarms } from "../lib/catalogue.server";
import { useLocaleContext } from "../lib/i18n/context";
import { seoMeta } from "../lib/seo";
import { useSiteSettings } from "../lib/site-settings";

export async function loader({ context }: Route.LoaderArgs) {
  return { farms: await loadFarms(catalogueRuntime(context)) };
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
  const { t } = useLocaleContext();
  const { banners } = useSiteSettings();
  return (
    <>
      {/* Same banner frame as the homepage hero and the blog — see
          `PageBanner`. Left blank in Site Control, it renders as the plain
          gradient backdrop rather than an unrelated stock photo. */}
      <PageBanner
        imageUrl={banners.farmsImageUrl || null}
        imageAlt={banners.farmsImageAlt}
        eyebrow={t("farms.eyebrow")}
        heading={t("farms.heading")}
        description="The verified farms and collectives that grow the True Grit market."
      />

      <Section>
        <div className="grid gap-6 md:grid-cols-3">
          {loaderData.farms.map((farm) => (
            <Link
              key={farm.id}
              to={`/farms/${farm.slug}`}
              className="group rounded-md border border-line bg-surface p-6 shadow-card transition-transform duration-200 hover:-translate-y-0.5"
            >
              <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
                {t("farms.since", { year: farm.establishedYear })}
              </p>
              <h2 className="mt-2 font-display text-xl text-ink group-hover:text-brand">
                {farm.name}
              </h2>
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

      {/* The recruitment call sits after the farms, not before them: a grower
          deciding whether to apply wants to see who is already here first, and
          a customer browsing suppliers should not be interrupted by a pitch
          aimed at someone else. */}
      <Section>
        <div className="rounded-md border border-line bg-subtle p-8 md:flex md:items-center md:justify-between md:gap-8">
          <div className="max-w-2xl">
            <h2 className="font-display text-2xl text-ink">{t("farms.partnerHeading")}</h2>
            <p className="mt-2 text-sm text-ink-muted">{t("farms.partnerBody")}</p>
          </div>
          <Link
            to="/farms/partner"
            className="mt-5 inline-flex min-h-11 shrink-0 items-center rounded-sm bg-brand px-6 text-sm font-medium text-ink-inverse hover:opacity-90 md:mt-0"
          >
            {t("farms.partnerButton")}
          </Link>
        </div>
      </Section>
    </>
  );
}
