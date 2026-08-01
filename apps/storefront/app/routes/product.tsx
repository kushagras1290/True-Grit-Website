import { useState } from "react";
import { data, Link } from "react-router";

import type { Route } from "./+types/product";
import {
  AvailabilityNote,
  Breadcrumbs,
  ProduceFrame,
  ProductGrid,
  Section,
} from "../components/catalogue";
import { ContactForm } from "../components/contact-form";
import { catalogueRuntime, loadProduct, loadProductsBySlugs } from "../lib/catalogue.server";
import { useCart } from "../lib/cart";
import { usePriceFormatter } from "../lib/currency";
import { resolveCountry } from "../lib/geo.server";
import { seoMeta } from "../lib/seo";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const country = resolveCountry(request);
  const runtime = catalogueRuntime(context);
  const product = await loadProduct(params.slug, country, runtime);
  if (!product) throw data("Product not found", { status: 404 });
  return { product, related: await loadProductsBySlugs(product.relatedSlugs, country, runtime) };
}

export function meta({ data: loaderData }: Route.MetaArgs) {
  return seoMeta(loaderData?.product.seo);
}

export default function ProductPage({ loaderData }: Route.ComponentProps) {
  const { product, related } = loaderData;
  const { add } = useCart();
  const formatPrice = usePriceFormatter();
  const [variantId, setVariantId] = useState(product.variants[0]?.id ?? "");
  const [quantity, setQuantity] = useState(1);
  const [added, setAdded] = useState(false);

  const variant = product.variants.find((entry) => entry.id === variantId) ?? product.variants[0];
  const price = variant ? (variant.saleMinor ?? variant.listMinor) : product.priceMinor;
  // Two independent gates on purchasability: out of stock is a variant-level,
  // usually-temporary state; `acceptsOrders` is the per-product kill-switch an
  // admin sets deliberately (mirroring Site Control's site-wide one, scoped to
  // just this item — see migration 0048). Both are re-checked server-side at
  // checkout, so this is UX, not the enforcement.
  const purchasable =
    product.acceptsOrders && (variant ? variant.availability !== "out_of_stock" : false);

  return (
    <>
      <Breadcrumbs
        items={[
          { label: "Home", path: "/" },
          { label: "Shop", path: "/shop" },
          { label: product.name, path: `/product/${product.slug}` },
        ]}
      />

      <div className="mx-auto grid max-w-[80rem] gap-10 px-4 py-8 sm:px-6 lg:grid-cols-2">
        <ProduceFrame
          slug={product.slug}
          alt={product.imageAlt}
          imageUrl={product.imageUrl}
          className="aspect-square rounded-md"
        />

        <div className="max-w-xl">
          <p className="text-sm text-ink-muted">
            <Link to={`/farms/${product.farmSlug}`} className="text-brand hover:underline">
              {product.farmName}
            </Link>{" "}
            · {product.region}
          </p>
          <h1 className="mt-1.5 font-display text-3xl leading-tight text-ink">{product.name}</h1>
          <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-subtle px-3 py-1 text-xs font-medium text-brand">
            <span aria-hidden>✓</span> {product.certification}
          </p>

          <p className="mt-5 text-2xl font-semibold text-ink">
            {formatPrice(price)}{" "}
            {variant && variant.saleMinor !== null ? (
              <s className="text-base font-normal text-ink-muted">
                {formatPrice(variant.listMinor)}
              </s>
            ) : null}
          </p>

          <fieldset className="mt-5">
            <legend className="text-sm font-medium text-ink">Size</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {product.variants.map((entry) => (
                <label
                  key={entry.id}
                  className={`flex min-h-11 cursor-pointer items-center rounded-sm border px-3.5 text-sm ${
                    entry.id === variantId
                      ? "border-brand bg-subtle/60 font-medium text-brand"
                      : "border-line-strong text-ink hover:border-brand"
                  } ${entry.availability === "out_of_stock" ? "opacity-50" : ""}`}
                >
                  <input
                    type="radio"
                    name="variant"
                    value={entry.id}
                    checked={entry.id === variantId}
                    onChange={() => setVariantId(entry.id)}
                    className="sr-only"
                  />
                  {entry.name}
                </label>
              ))}
            </div>
          </fieldset>

          <div className="mt-5 flex items-end gap-3">
            <div>
              <label htmlFor="quantity" className="block text-sm font-medium text-ink">
                Quantity
              </label>
              <div className="mt-2 flex items-center rounded-sm border border-line-strong">
                <button
                  type="button"
                  aria-label="Decrease quantity"
                  className="min-h-11 min-w-11 text-lg"
                  onClick={() => setQuantity((current) => Math.max(1, current - 1))}
                >
                  −
                </button>
                <input
                  id="quantity"
                  inputMode="numeric"
                  readOnly
                  value={quantity}
                  className="w-10 border-x border-line-strong text-center text-sm"
                />
                <button
                  type="button"
                  aria-label="Increase quantity"
                  className="min-h-11 min-w-11 text-lg"
                  onClick={() => setQuantity((current) => Math.min(12, current + 1))}
                >
                  +
                </button>
              </div>
            </div>
            <button
              type="button"
              disabled={!purchasable}
              onClick={() => {
                if (!variant) return;
                add(
                  {
                    productSlug: product.slug,
                    productName: product.name,
                    variantId: variant.id,
                    variantName: variant.name,
                    unitMinor: variant.saleMinor ?? variant.listMinor,
                  },
                  quantity,
                );
                setAdded(true);
                setTimeout(() => setAdded(false), 2000);
              }}
              className="min-h-11 flex-1 rounded-sm bg-brand px-6 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {!product.acceptsOrders
                ? "Not available to order"
                : purchasable
                  ? "Add to basket"
                  : "Out of stock"}
            </button>
          </div>
          <p role="status" className="mt-2 min-h-5 text-sm text-success">
            {added ? "Added to your basket." : ""}
          </p>
          {/* The per-product switch takes priority over ordinary stock status in
              the wording: an admin turned ordering off deliberately, which reads
              differently from "we sold out and will restock" — but both leave
              the customer with nothing to click, so both get the same interest
              form below rather than a dead end. */}
          {!product.acceptsOrders ? (
            <p className="mt-2 text-sm text-ink-muted">
              We are not taking orders for this product right now. Leave your details below and we
              will let you know when it is back.
            </p>
          ) : variant ? (
            <AvailabilityNote availability={variant.availability} />
          ) : null}

          <div className="mt-8 space-y-4 border-t border-line pt-6 text-sm">
            <p className="text-ink">{product.overview}</p>
            {product.harvestNote ? (
              <p className="text-ink-muted">
                <span className="font-medium text-ink">Harvest: </span>
                {product.harvestNote}
              </p>
            ) : null}
            {product.storageGuidance ? (
              <p className="text-ink-muted">
                <span className="font-medium text-ink">Storage: </span>
                {product.storageGuidance}
              </p>
            ) : null}
            <p className="text-ink-muted">
              <span className="font-medium text-ink">Returns: </span>
              {product.returnEligible
                ? "Eligible for return — see our returns policy."
                : "Not eligible for return due to the nature of this product."}
            </p>
          </div>

          {/* Same fallback the checkout page shows when ordering is off
              site-wide (components/contact-form.tsx) — here it is scoped to
              this one product rather than the whole basket, and it covers
              both reasons "Add to basket" is unavailable: the admin switch
              (acceptsOrders) and ordinary out-of-stock. Either way the
              customer is left with nothing to click, so either way they get a
              way to leave their details instead of a dead end. */}
          {!purchasable ? (
            <div className="mt-8 border-t border-line pt-6">
              <h2 className="font-display text-lg text-ink">Interested in this product?</h2>
              <p className="mt-1 text-sm text-ink-muted">
                We will get in touch as soon as {product.name} is available to order again.
              </p>
              <div className="mt-4">
                <ContactForm
                  compact
                  defaultSubject={`Interest: ${product.name}`}
                  messagePlaceholder={`Let us know how much ${product.name} you would like and where it would be delivered.`}
                  submitLabel="Send enquiry"
                  successMessage="Thanks — we have your details and will be in touch as soon as this is back."
                />
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <Section eyebrow="Trace your food" heading="From the farm to your door" tone="subtle">
        <ol className="mx-auto grid max-w-4xl gap-6 sm:grid-cols-2 lg:grid-cols-5">
          {product.traceability.map((step, index) => (
            <li key={step.label} className="relative">
              <span className="font-display text-2xl text-accent">{index + 1}</span>
              <p className="mt-1 font-medium text-ink">{step.label}</p>
              <p className="mt-1 text-sm text-ink-muted">{step.detail}</p>
            </li>
          ))}
        </ol>
      </Section>

      {related.length > 0 ? (
        <Section eyebrow="Goes well with" heading="From the same soil">
          <ProductGrid products={related} />
        </Section>
      ) : null}
    </>
  );
}
