import { formatMoney } from "@truegrit/contracts";
import { useState } from "react";
import { data, Link } from "react-router";

import type { Route } from "./+types/bundle";
import { Section } from "../components/catalogue";
import { PageBanner } from "../components/page-banner";
import { catalogueRuntime, loadBundle } from "../lib/catalogue.server";
import { useCart } from "../lib/cart";
import { mediaUrl } from "../lib/media";
import { seoMeta } from "../lib/seo";
import { LocalizedText } from "../lib/i18n/localized-text";
import { resolveLocale } from "../lib/i18n/resolve.server";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const { locale } = resolveLocale(request);
  const bundle = await loadBundle(params.slug, catalogueRuntime(context), locale.code);
  if (!bundle) throw data("Bundle not found", { status: 404 });
  return { bundle };
}

export function meta({ data: loaderData, matches }: Route.MetaArgs) {
  if (!loaderData) return seoMeta(null, matches);
  return seoMeta(
    {
      title: loaderData.bundle.name,
      description:
        loaderData.bundle.description || `${loaderData.bundle.name} — a True Grit bundle.`,
      canonicalPath: `/bundles/${loaderData.bundle.slug}`,
      indexing: "index",
    },
    matches,
  );
}

export default function BundlePage({ loaderData }: Route.ComponentProps) {
  const { bundle } = loaderData;
  const { add } = useCart();
  const [added, setAdded] = useState(false);

  return (
    <>
      <PageBanner
        imageUrl={bundle.imageUrl || "/banners/home/09-build-a-better-breakfast.webp"}
        imageAlt={bundle.imageAlt || bundle.name}
        eyebrow="Buy together and save"
        heading={bundle.name}
        description={bundle.description}
      />

      <Section>
        <div className="grid gap-10 md:grid-cols-[1fr_20rem]">
          <div>
            <h2 className="text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
              <LocalizedText>What&apos;s in this bundle</LocalizedText>
            </h2>
            <ul className="mt-3 divide-y divide-line rounded-md border border-line bg-surface">
              {bundle.items.map((item) => (
                <li key={item.variantId} className="flex items-center gap-4 px-4 py-3">
                  {item.imageUrl ? (
                    <img
                      src={mediaUrl(item.imageUrl)}
                      alt=""
                      className="h-14 w-14 shrink-0 rounded-sm bg-subtle object-contain p-1"
                    />
                  ) : (
                    <span aria-hidden className="h-14 w-14 shrink-0 rounded-sm bg-subtle" />
                  )}
                  <div className="min-w-0 flex-1">
                    <Link
                      to={`/product/${item.productSlug}`}
                      className="block truncate text-sm font-medium text-ink hover:text-brand"
                    >
                      {item.productName}
                    </Link>
                    <p className="text-xs text-ink-muted">
                      {item.variantName} · {item.quantity} × {formatMoney(item.unitPriceMinor)}
                    </p>
                  </div>
                  <p className="shrink-0 text-sm text-ink">{formatMoney(item.lineTotalMinor)}</p>
                </li>
              ))}
            </ul>
          </div>

          <aside className="h-fit rounded-md border border-line bg-surface p-5 shadow-card">
            <dl className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-muted">
                  <LocalizedText>Priced separately</LocalizedText>
                </dt>
                <dd className="text-ink-muted line-through">
                  {formatMoney(bundle.componentSumMinor)}
                </dd>
              </div>
              <div className="flex justify-between border-t border-line pt-1.5 font-medium">
                <dt>
                  <LocalizedText>Bundle price</LocalizedText>
                </dt>
                <dd>{formatMoney(bundle.bundlePriceMinor)}</dd>
              </div>
              {bundle.savingsMinor > 0 ? (
                <p className="!mt-2 text-xs font-medium text-success">
                  <LocalizedText>You save</LocalizedText> {formatMoney(bundle.savingsMinor)}
                </p>
              ) : null}
            </dl>
            <button
              type="button"
              className="mt-4 min-h-11 w-full rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-95"
              onClick={() => {
                for (const item of bundle.items) {
                  add(
                    {
                      productSlug: item.productSlug,
                      productName: item.productName,
                      variantId: item.variantId,
                      variantName: item.variantName,
                      unitMinor: item.unitPriceMinor,
                    },
                    item.quantity,
                  );
                }
                setAdded(true);
              }}
            >
              {added ? (
                <LocalizedText>{"Added to basket"}</LocalizedText>
              ) : (
                <LocalizedText>{"Add bundle to basket"}</LocalizedText>
              )}
            </button>
            <p className="mt-2 text-xs text-ink-muted">
              <LocalizedText>
                Every item goes into your basket at its own price; the bundle saving is applied at
                checkout once your basket holds the full set.
              </LocalizedText>
            </p>
            {added ? (
              <Link
                to="/cart"
                className="mt-3 block text-center text-sm font-medium text-brand hover:underline"
              >
                <LocalizedText>View basket</LocalizedText>
              </Link>
            ) : null}
          </aside>
        </div>
      </Section>
    </>
  );
}
