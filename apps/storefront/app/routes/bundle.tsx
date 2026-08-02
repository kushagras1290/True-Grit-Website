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

export async function loader({ params, context }: Route.LoaderArgs) {
  const bundle = await loadBundle(params.slug, catalogueRuntime(context));
  if (!bundle) throw data("Bundle not found", { status: 404 });
  return { bundle };
}

export function meta({ data: loaderData }: Route.MetaArgs) {
  if (!loaderData) return seoMeta(null);
  return seoMeta({
    title: loaderData.bundle.name,
    description: loaderData.bundle.description || `${loaderData.bundle.name} — a True Grit bundle.`,
    canonicalPath: `/bundles/${loaderData.bundle.slug}`,
    indexing: "index",
  });
}

export default function BundlePage({ loaderData }: Route.ComponentProps) {
  const { bundle } = loaderData;
  const { add } = useCart();
  const [added, setAdded] = useState(false);

  return (
    <>
      <PageBanner
        imageUrl={bundle.imageUrl}
        imageAlt={bundle.imageAlt || bundle.name}
        eyebrow="Buy together and save"
        heading={bundle.name}
        description={bundle.description}
      />

      <Section>
        <div className="grid gap-10 md:grid-cols-[1fr_20rem]">
          <div>
            <h2 className="text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
              What&apos;s in this bundle
            </h2>
            <ul className="mt-3 divide-y divide-line rounded-md border border-line bg-surface">
              {bundle.items.map((item) => (
                <li key={item.variantId} className="flex items-center gap-4 px-4 py-3">
                  {item.imageUrl ? (
                    <img
                      src={mediaUrl(item.imageUrl)}
                      alt=""
                      className="h-14 w-14 shrink-0 rounded-sm object-cover"
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
                      {item.variantName} · {item.quantity} ×{" "}
                      {formatMoney(item.unitPriceMinor)}
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
                <dt className="text-ink-muted">Priced separately</dt>
                <dd className="text-ink-muted line-through">
                  {formatMoney(bundle.componentSumMinor)}
                </dd>
              </div>
              <div className="flex justify-between border-t border-line pt-1.5 font-medium">
                <dt>Bundle price</dt>
                <dd>{formatMoney(bundle.bundlePriceMinor)}</dd>
              </div>
              {bundle.savingsMinor > 0 ? (
                <p className="!mt-2 text-xs font-medium text-success">
                  You save {formatMoney(bundle.savingsMinor)}
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
              {added ? "Added to basket" : "Add bundle to basket"}
            </button>
            <p className="mt-2 text-xs text-ink-muted">
              Every item goes into your basket at its own price; the bundle saving is applied at
              checkout once your basket holds the full set.
            </p>
            {added ? (
              <Link
                to="/cart"
                className="mt-3 block text-center text-sm font-medium text-brand hover:underline"
              >
                View basket
              </Link>
            ) : null}
          </aside>
        </div>
      </Section>
    </>
  );
}
