import { formatMoney } from "@truegrit/contracts";
import { Link } from "react-router";

import type { Route } from "./+types/bundles";
import { Section } from "../components/catalogue";
import { PageBanner } from "../components/page-banner";
import { PageLinkPagination } from "../components/pagination";
import { catalogueRuntime, loadBundles } from "../lib/catalogue.server";
import { mediaUrl } from "../lib/media";
import { seoMeta } from "../lib/seo";
import { LocalizedText } from "../lib/i18n/localized-text";

const BUNDLE_PAGE_SIZE = 12;

export async function loader({ context, request }: Route.LoaderArgs) {
  const page = Math.max(1, Number(new URL(request.url).searchParams.get("page")) || 1);
  return {
    page,
    pageSize: BUNDLE_PAGE_SIZE,
    bundles: await loadBundles(page, BUNDLE_PAGE_SIZE, catalogueRuntime(context)),
  };
}

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Bundles",
    description: "Curated sets of market favourites, bought together at a set price.",
    canonicalPath: "/bundles",
    indexing: "index",
  });
}

export default function BundlesPage({ loaderData }: Route.ComponentProps) {
  const { bundles } = loaderData;
  return (
    <>
      <PageBanner
        imageUrl={bundles.items[0]?.imageUrl || "/banners/home/09-build-a-better-breakfast.webp"}
        imageAlt="A curated set of True Grit products"
        eyebrow="Buy together and save"
        heading="Bundles"
        description="Curated sets of market favourites at a set price — added to your basket together, in one click."
      />
      <Section eyebrow="Browse bundles" heading="Set combinations, set prices">
        {bundles.items.length === 0 ? (
          <p className="text-sm text-ink-muted">
            <LocalizedText>No bundles are live right now — check back soon.</LocalizedText>
          </p>
        ) : (
          <>
            <p className="mb-5 text-sm text-ink-muted" role="status">
              {bundles.total} <LocalizedText>bundle</LocalizedText>
              {bundles.total === 1 ? "" : "s"}
            </p>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {bundles.items.map((bundle) => (
                <Link
                  key={bundle.id}
                  to={`/bundles/${bundle.slug}`}
                  className="group overflow-hidden rounded-md border border-line bg-surface p-6 shadow-card transition-transform duration-200 hover:-translate-y-0.5"
                >
                  {bundle.imageUrl ? (
                    <img
                      src={mediaUrl(bundle.imageUrl)}
                      alt={bundle.imageAlt || ""}
                      loading="lazy"
                      className="-mx-6 -mt-6 mb-5 aspect-[16/9] w-[calc(100%+3rem)] max-w-none bg-subtle object-contain"
                    />
                  ) : null}
                  <h2 className="font-display text-xl text-ink group-hover:text-brand">
                    {bundle.name}
                  </h2>
                  {bundle.description ? (
                    <p className="mt-2 text-sm text-ink-muted">{bundle.description}</p>
                  ) : null}
                  <p className="mt-3 text-xs text-ink-muted">
                    {bundle.items.length} <LocalizedText>item</LocalizedText>
                    {bundle.items.length === 1 ? "" : "s"}
                  </p>
                  <p className="mt-3 flex items-baseline gap-2">
                    <span className="font-display text-lg text-ink">
                      {formatMoney(bundle.bundlePriceMinor)}
                    </span>
                    {bundle.savingsMinor > 0 ? (
                      <span className="text-xs font-medium text-success">
                        <LocalizedText>Save</LocalizedText> {formatMoney(bundle.savingsMinor)}
                      </span>
                    ) : null}
                  </p>
                </Link>
              ))}
            </div>
            <PageLinkPagination
              page={loaderData.page}
              pageSize={loaderData.pageSize}
              total={bundles.total}
            />
          </>
        )}
      </Section>
    </>
  );
}
