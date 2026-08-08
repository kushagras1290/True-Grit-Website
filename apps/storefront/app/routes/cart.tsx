import type { ProductSummary } from "@truegrit/contracts";
import { useEffect, useState } from "react";
import { Link } from "react-router";

import type { Route } from "./+types/cart";
import { Section } from "../components/catalogue";
import { RecommendedProducts } from "../components/recommendations";
import { useCart } from "../lib/cart";
import { commerceLive, getBestsellers } from "../lib/commerce";
import { usePriceFormatter } from "../lib/currency";
import { seoMeta } from "../lib/seo";
import { useSiteSettings } from "../lib/site-settings";
import { LocalizedText, useLocalizeFormat } from "../lib/i18n/localized-text";

export function meta({ matches }: Route.MetaArgs) {
  return seoMeta(
    {
      title: "Your basket",
      description: "Review your basket before checkout.",
      canonicalPath: "/cart",
      indexing: "noindex",
    },
    matches,
  );
}

export default function CartPage(_props: Route.ComponentProps) {
  const { lines, subtotalMinor, setQuantity, remove } = useCart();
  const { payments, recommendations } = useSiteSettings();
  const formatPrice = usePriceFormatter();
  const format = useLocalizeFormat();

  // Client-side, not the server loader: the basket only exists in
  // localStorage, so only the browser knows which slugs to exclude. Re-fetches
  // whenever the basket's contents change, so a newly added item drops out of
  // its own "you might also like" row.
  const [recommended, setRecommended] = useState<ProductSummary[]>([]);
  const cartSlugs = lines.map((line) => line.productSlug).join(",");
  useEffect(() => {
    if (!commerceLive || !recommendations.enabled) return;
    let active = true;
    getBestsellers({ excludeSlugs: cartSlugs ? cartSlugs.split(",") : undefined })
      .then((items) => {
        if (active) setRecommended(items);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cartSlugs, recommendations.enabled]);

  if (lines.length === 0) {
    return (
      <>
        <Section eyebrow="Your basket" heading="Nothing in the basket yet">
          <p className="max-w-md text-sm text-ink-muted">
            <LocalizedText>
              The market is open. Seasonal fruit, honest staples and slow-pressed oils are a click
              away.
            </LocalizedText>
          </p>
          <Link
            to="/shop"
            className="mt-5 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
          >
            <LocalizedText>Explore the market</LocalizedText>
          </Link>
        </Section>
        <RecommendedProducts
          eyebrow="Popular this week"
          heading="Start here"
          products={recommended}
        />
      </>
    );
  }

  return (
    <>
      <Section
        eyebrow="Your basket"
        heading={
          lines.length === 1
            ? format("{count} item", { count: lines.length })
            : format("{count} items", { count: lines.length })
        }
      >
        <div className="grid gap-10 lg:grid-cols-[2fr_1fr]">
          <ul className="divide-y divide-line">
            {lines.map((line) => (
              <li
                key={`${line.variantId}:${line.preorder ? "preorder" : "standard"}`}
                className="flex flex-wrap items-center gap-4 py-5"
              >
                <div className="min-w-0 flex-1">
                  <Link
                    to={`/product/${line.productSlug}`}
                    className="font-medium text-ink hover:text-brand"
                  >
                    {line.productName}
                  </Link>
                  <p className="text-sm text-ink-muted">{line.variantName}</p>
                  {line.preorder ? (
                    <p className="mt-1 text-xs font-medium text-accent"><LocalizedText>Harvest pre-order</LocalizedText></p>
                  ) : null}
                </div>
                <div className="flex items-center rounded-sm border border-line-strong">
                  <button
                    type="button"
                    aria-label={format("Decrease quantity of {product}", {
                      product: line.productName,
                    })}
                    className="min-h-11 min-w-11 text-lg"
                    onClick={() => setQuantity(line.variantId, line.quantity - 1, line.preorder)}
                  >
                    −
                  </button>
                  <span aria-live="polite" className="w-8 text-center text-sm">
                    {line.quantity}
                  </span>
                  <button
                    type="button"
                    aria-label={format("Increase quantity of {product}", {
                      product: line.productName,
                    })}
                    className="min-h-11 min-w-11 text-lg"
                    onClick={() => setQuantity(line.variantId, line.quantity + 1, line.preorder)}
                  >
                    +
                  </button>
                </div>
                <p className="w-24 text-right font-medium text-ink">
                  {formatPrice(line.unitMinor * line.quantity)}
                </p>
                <button
                  type="button"
                  onClick={() => remove(line.variantId, line.preorder)}
                  className="text-sm text-ink-muted underline-offset-4 hover:text-danger hover:underline"
                >
                  <LocalizedText>Remove</LocalizedText>
                </button>
              </li>
            ))}
          </ul>

          <aside className="h-fit rounded-md border border-line bg-surface p-5 shadow-card">
            <h2 className="font-display text-lg text-ink">
              <LocalizedText>Order summary</LocalizedText>
            </h2>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-muted">
                  <LocalizedText>Subtotal (estimate)</LocalizedText>
                </dt>
                <dd className="font-medium text-ink">{formatPrice(subtotalMinor)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">
                  <LocalizedText>Delivery</LocalizedText>
                </dt>
                <dd className="text-ink-muted">
                  <LocalizedText>Calculated at checkout</LocalizedText>
                </dd>
              </div>
            </dl>
            {/* Ordering switched off in the admin console: the checkout route
                already handles this, but sending someone through a button that
                says "checkout" only to tell them they cannot is worse than saying
                so here. The basket itself is untouched. */}
            {payments.enabled ? (
              <>
                <Link
                  to="/checkout"
                  className="mt-5 flex min-h-11 w-full items-center justify-center rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-90"
                >
                  <LocalizedText>Proceed to checkout</LocalizedText>
                </Link>
                <p className="mt-2 text-xs text-ink-muted">
                  <LocalizedText>
                    Prices are re-validated server-side at checkout; your basket total here is an
                    estimate.
                  </LocalizedText>
                </p>
              </>
            ) : (
              <>
                <p className="mt-5 rounded-sm border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
                  {payments.disabledNotice}
                </p>
                <Link
                  to="/checkout"
                  className="mt-3 flex min-h-11 w-full items-center justify-center rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-90"
                >
                  <LocalizedText>Register your interest</LocalizedText>
                </Link>
              </>
            )}
          </aside>
        </div>
      </Section>
      <RecommendedProducts
        eyebrow="Frequently added"
        heading="You might also like"
        products={recommended}
      />
    </>
  );
}
