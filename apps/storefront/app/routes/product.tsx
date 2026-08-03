import { useState } from "react";
import { data, Link } from "react-router";

import type { Route } from "./+types/product";
import {
  AvailabilityNote,
  Breadcrumbs,
  ProductGrid,
  Section,
} from "../components/catalogue";
import { ContactForm } from "../components/contact-form";
import { ProductGallery } from "../components/product-gallery";
import { ProductReviews, RatingSummary } from "../components/reviews";
import { RecommendedProducts } from "../components/recommendations";
import { SubscribeAndSave } from "../components/subscribe-and-save";
import {
  catalogueRuntime,
  loadAlsoBought,
  loadProduct,
  loadProductReviews,
  loadProductsBySlugs,
} from "../lib/catalogue.server";
import { useCart } from "../lib/cart";
import { usePriceFormatter } from "../lib/currency";
import { resolveCountry } from "../lib/geo.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { productEffectivePrice, variantEffectivePrice } from "../lib/pricing";
import { seoMeta } from "../lib/seo";
import { useSiteSettings } from "../lib/site-settings";

export async function loader({ params, request, context }: Route.LoaderArgs) {
  const country = resolveCountry(request);
  const { locale } = resolveLocale(request);
  const runtime = catalogueRuntime(context);
  const product = await loadProduct(params.slug, country, runtime, locale.code);
  if (!product) throw data("Product not found", { status: 404 });
  const [related, reviews, alsoBought] = await Promise.all([
    loadProductsBySlugs(product.relatedSlugs, country, runtime, locale.code),
    loadProductReviews(product.slug, runtime),
    loadAlsoBought(product.slug, 6, country, runtime, locale.code),
  ]);
  return { product, related, reviews, alsoBought };
}

export function meta({ data: loaderData }: Route.MetaArgs) {
  return seoMeta(loaderData?.product.seo);
}

export default function ProductPage({ loaderData }: Route.ComponentProps) {
  const { product, related, reviews, alsoBought } = loaderData;
  const { add } = useCart();
  const formatPrice = usePriceFormatter();
  const { payments } = useSiteSettings();
  const [variantId, setVariantId] = useState(product.variants[0]?.id ?? "");
  const [quantity, setQuantity] = useState(1);
  const [added, setAdded] = useState(false);

  const variant = product.variants.find((entry) => entry.id === variantId) ?? product.variants[0];
  const effective = variant ? variantEffectivePrice(variant) : productEffectivePrice(product);
  // Three independent gates on purchasability, all re-checked server-side at
  // checkout (this is UX, not the enforcement):
  // - out of stock: a variant-level, usually-temporary state.
  // - `acceptsOrders`: the per-product stock/quality kill-switch (migration
  //   0048), always narrowing regardless of the site-wide payments switch.
  // - `paymentsOverride`: this product's own divergence from the site-wide
  //   payments switch (migration 0069) -- "inherit" follows `payments.enabled`,
  //   "force_enabled" buys even while it is off, "force_disabled" blocks even
  //   while it is on.
  const paymentsAllowed =
    product.paymentsOverride === "inherit"
      ? payments.enabled
      : product.paymentsOverride === "force_enabled";
  const purchasable =
    product.acceptsOrders &&
    paymentsAllowed &&
    (variant ? variant.availability !== "out_of_stock" : false);

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
        <ProductGallery
          slug={product.slug}
          mainImageUrl={product.imageUrl}
          mainImageAlt={product.imageAlt}
          galleryImages={product.images ?? []}
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
          <div className="mt-2 flex flex-wrap items-center gap-2.5">
            <p className="inline-flex items-center gap-1.5 rounded-full bg-subtle px-3 py-1 text-xs font-medium text-brand">
              <span aria-hidden>✓</span> {product.certification}
            </p>
            {product.ratingCount > 0 ? (
              <a href="#reviews" className="text-sm text-ink hover:underline">
                <RatingSummary average={product.ratingAverage} count={product.ratingCount} />
              </a>
            ) : null}
          </div>

          <p className="mt-5 text-2xl font-semibold text-ink">
            {formatPrice(effective.amountMinor)}{" "}
            {effective.originalMinor !== null ? (
              <s className="text-base font-normal text-ink-muted">
                {formatPrice(effective.originalMinor)}
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
                    unitMinor: variantEffectivePrice(variant).amountMinor,
                  },
                  quantity,
                );
                setAdded(true);
                setTimeout(() => setAdded(false), 2000);
              }}
              className="min-h-11 flex-1 rounded-sm bg-brand px-6 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {purchasable
                ? "Add to basket"
                : product.acceptsOrders && paymentsAllowed
                  ? "Out of stock"
                  : "Not available to order"}
            </button>
          </div>
          <p role="status" className="mt-2 min-h-5 text-sm text-success">
            {added ? "Added to your basket." : ""}
          </p>
          {/* Either admin switch (acceptsOrders, or paymentsOverride diverging
              from the site-wide payments switch) takes priority over ordinary
              stock status in the wording: an admin turned ordering off
              deliberately, which reads differently from "we sold out and will
              restock" — but all three leave the customer with nothing to
              click, so all three get the same interest form below rather than
              a dead end. */}
          {!product.acceptsOrders || !paymentsAllowed ? (
            <p className="mt-2 text-sm text-ink-muted">
              We are not taking orders for this product right now. Leave your details below and we
              will let you know when it is back.
            </p>
          ) : variant ? (
            <AvailabilityNote availability={variant.availability} />
          ) : null}

          {purchasable && variant ? (
            <SubscribeAndSave variantId={variant.id} quantity={quantity} productName={product.name} />
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
              every reason "Add to basket" is unavailable: the admin switch
              (acceptsOrders), this product's payments override diverging from
              the site-wide switch, and ordinary out-of-stock. Either way the
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

      <div id="reviews">
        <Section eyebrow="Customer reviews" heading={`Reviews for ${product.name}`} tone="subtle">
          <ProductReviews
            reviews={reviews}
            average={product.ratingAverage}
            count={product.ratingCount}
          />
        </Section>
      </div>

      {related.length > 0 ? (
        <Section eyebrow="Goes well with" heading="From the same soil">
          <ProductGrid products={related} />
        </Section>
      ) : null}

      <RecommendedProducts
        eyebrow="Frequently bought together"
        heading="Customers also bought"
        products={alsoBought}
        tone="subtle"
      />
    </>
  );
}
