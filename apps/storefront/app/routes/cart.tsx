import { Link } from "react-router";

import type { Route } from "./+types/cart";
import { Section } from "../components/catalogue";
import { useCart } from "../lib/cart";
import { usePriceFormatter } from "../lib/currency";
import { seoMeta } from "../lib/seo";
import { useSiteSettings } from "../lib/site-settings";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Your basket",
    description: "Review your basket before checkout.",
    canonicalPath: "/cart",
    indexing: "noindex",
  });
}

export default function CartPage(_props: Route.ComponentProps) {
  const { lines, subtotalMinor, setQuantity, remove } = useCart();
  const { payments } = useSiteSettings();
  const formatPrice = usePriceFormatter();

  if (lines.length === 0) {
    return (
      <Section eyebrow="Your basket" heading="Nothing in the basket yet">
        <p className="max-w-md text-sm text-ink-muted">
          The market is open. Seasonal fruit, honest staples and slow-pressed oils are a click away.
        </p>
        <Link
          to="/shop"
          className="mt-5 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
        >
          Explore the market
        </Link>
      </Section>
    );
  }

  return (
    <Section eyebrow="Your basket" heading={`${lines.length} item${lines.length === 1 ? "" : "s"}`}>
      <div className="grid gap-10 lg:grid-cols-[2fr_1fr]">
        <ul className="divide-y divide-line">
          {lines.map((line) => (
            <li key={line.variantId} className="flex flex-wrap items-center gap-4 py-5">
              <div className="min-w-0 flex-1">
                <Link
                  to={`/product/${line.productSlug}`}
                  className="font-medium text-ink hover:text-brand"
                >
                  {line.productName}
                </Link>
                <p className="text-sm text-ink-muted">{line.variantName}</p>
              </div>
              <div className="flex items-center rounded-sm border border-line-strong">
                <button
                  type="button"
                  aria-label={`Decrease quantity of ${line.productName}`}
                  className="min-h-11 min-w-11 text-lg"
                  onClick={() => setQuantity(line.variantId, line.quantity - 1)}
                >
                  −
                </button>
                <span aria-live="polite" className="w-8 text-center text-sm">
                  {line.quantity}
                </span>
                <button
                  type="button"
                  aria-label={`Increase quantity of ${line.productName}`}
                  className="min-h-11 min-w-11 text-lg"
                  onClick={() => setQuantity(line.variantId, line.quantity + 1)}
                >
                  +
                </button>
              </div>
              <p className="w-24 text-right font-medium text-ink">
                {formatPrice(line.unitMinor * line.quantity)}
              </p>
              <button
                type="button"
                onClick={() => remove(line.variantId)}
                className="text-sm text-ink-muted underline-offset-4 hover:text-danger hover:underline"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>

        <aside className="h-fit rounded-md border border-line bg-surface p-5 shadow-card">
          <h2 className="font-display text-lg text-ink">Order summary</h2>
          <dl className="mt-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-muted">Subtotal (estimate)</dt>
              <dd className="font-medium text-ink">{formatPrice(subtotalMinor)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-muted">Delivery</dt>
              <dd className="text-ink-muted">Calculated at checkout</dd>
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
                Proceed to checkout
              </Link>
              <p className="mt-2 text-xs text-ink-muted">
                Prices are re-validated server-side at checkout; your basket total here is an
                estimate.
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
                Register your interest
              </Link>
            </>
          )}
        </aside>
      </div>
    </Section>
  );
}
