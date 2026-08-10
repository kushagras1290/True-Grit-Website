import { useEffect, useState } from "react";
import { data, Link, useSearchParams } from "react-router";

import type { Route } from "./+types/product";
import { AvailabilityNote, Breadcrumbs, ProductGrid, Section } from "../components/catalogue";
import { ContactForm } from "../components/contact-form";
import { ProductGallery } from "../components/product-gallery";
import { ProductQrCode } from "../components/product-qr-code";
import { ProductReviews, RatingSummary } from "../components/reviews";
import { RecommendedProducts } from "../components/recommendations";
import { SubscribeAndSave } from "../components/subscribe-and-save";
import { WishlistButton } from "../components/wishlist-button";
import {
  catalogueRuntime,
  loadAlsoBought,
  loadProduct,
  loadProductReviews,
  loadProductsBySlugs,
} from "../lib/catalogue.server";
import { useCart } from "../lib/cart";
import { commerceLive, getB2BPriceBreaks, type B2BPriceBreakInfo } from "../lib/commerce";
import { usePriceFormatter } from "../lib/currency";
import { resolveCountry } from "../lib/geo.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { mediaUrl } from "../lib/media";
import { productEffectivePrice, variantEffectivePrice } from "../lib/pricing";
import { breadcrumbJsonLd, productJsonLd, seoMeta } from "../lib/seo";
import { useSiteSettings } from "../lib/site-settings";
import { LocalizedText, useLocalizeFormat, useLocalizeText } from "../lib/i18n/localized-text";

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
  // Absolute, not root-relative: a QR code has to resolve on whatever device
  // scans it, unlike the canonical <link> tag which the browser/crawler
  // already resolves against the current page. Derived from the actual
  // incoming request rather than a config constant so it's automatically
  // correct on a custom domain, a preview URL, or local dev alike.
  const origin = new URL(request.url).origin;
  return { product, related, reviews, alsoBought, origin };
}

export function meta({ data: loaderData, matches }: Route.MetaArgs) {
  if (!loaderData) return seoMeta(null, matches);
  const { product } = loaderData;
  const effective = productEffectivePrice(product);
  return [
    ...seoMeta(product.seo, matches),
    productJsonLd({
      name: product.name,
      description: product.shortDescription || product.overview,
      canonicalPath: product.seo.canonicalPath,
      sku: product.variants[0]?.sku,
      priceMinor: effective.amountMinor,
      currencyCode: product.currencyCode,
      availability: product.availability,
      imageUrl: mediaUrl(product.imageUrl),
    }),
    breadcrumbJsonLd([
      { name: "Home", path: "/" },
      { name: "Shop", path: "/shop" },
      { name: product.name, path: product.seo.canonicalPath },
    ]),
  ];
}

export default function ProductPage({ loaderData }: Route.ComponentProps) {
  const format = useLocalizeFormat();
  const localize = useLocalizeText();
  const { product, related, reviews, alsoBought, origin } = loaderData;
  const { add } = useCart();
  const formatPrice = usePriceFormatter();
  const { payments, preorders, b2b } = useSiteSettings();
  const [searchParams] = useSearchParams();
  const preorderRequested = preorders.enabled && searchParams.get("preorder") === "1";
  const [variantId, setVariantId] = useState(product.variants[0]?.id ?? "");
  const [quantity, setQuantity] = useState(1);
  const [added, setAdded] = useState(false);
  const [bulkPrices, setBulkPrices] = useState<B2BPriceBreakInfo[]>([]);

  const variant = product.variants.find((entry) => entry.id === variantId) ?? product.variants[0];
  const effective = variant ? variantEffectivePrice(variant) : productEffectivePrice(product);
  const applicableBulkPrice = [...bulkPrices]
    .filter((price) => price.minQuantity <= quantity)
    .sort((left, right) => right.minQuantity - left.minQuantity)[0];
  const unitMinor = applicableBulkPrice
    ? Math.min(effective.amountMinor, applicableBulkPrice.priceMinor)
    : effective.amountMinor;

  useEffect(() => {
    if (!commerceLive || !b2b.enabled || !variant?.id) {
      setBulkPrices([]);
      return;
    }
    let active = true;
    getB2BPriceBreaks(variant.id)
      .then((prices) => {
        if (active) setBulkPrices(prices);
      })
      .catch(() => setBulkPrices([]));
    return () => {
      active = false;
    };
  }, [b2b.enabled, variant?.id]);
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
    (preorderRequested || (variant ? variant.availability !== "out_of_stock" : false));

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
            {product.certifications.map((certification) => (
              <p
                key={certification}
                className="inline-flex items-center gap-1.5 rounded-full bg-subtle px-3 py-1 text-xs font-medium text-brand"
              >
                <span aria-hidden>✓</span> {certification}
              </p>
            ))}
            {product.ratingCount > 0 ? (
              <a href="#reviews" className="text-sm text-ink hover:underline">
                <RatingSummary average={product.ratingAverage} count={product.ratingCount} />
              </a>
            ) : null}
          </div>

          <p className="mt-5 text-2xl font-semibold text-ink">
            {formatPrice(unitMinor)}{" "}
            {effective.originalMinor !== null ? (
              <s className="text-base font-normal text-ink-muted">
                {formatPrice(effective.originalMinor)}
              </s>
            ) : null}
          </p>

          <fieldset className="mt-5">
            <legend className="text-sm font-medium text-ink">
              <LocalizedText>Size</LocalizedText>
            </legend>
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
                <LocalizedText>Quantity</LocalizedText>
              </label>
              <div className="mt-2 flex items-center rounded-sm border border-line-strong">
                <button
                  type="button"
                  aria-label={localize("Decrease quantity")}
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
                  aria-label={localize("Increase quantity")}
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
                    unitMinor,
                    preorder: preorderRequested,
                  },
                  quantity,
                );
                setAdded(true);
                setTimeout(() => setAdded(false), 2000);
              }}
              className="min-h-11 flex-1 rounded-sm bg-brand px-6 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {purchasable ? (
                <LocalizedText>
                  {preorderRequested ? "Reserve harvest" : "Add to basket"}
                </LocalizedText>
              ) : product.acceptsOrders && paymentsAllowed ? (
                <LocalizedText>{"Out of stock"}</LocalizedText>
              ) : (
                <LocalizedText>{"Not available to order"}</LocalizedText>
              )}
            </button>
            <WishlistButton
              productId={product.id}
              className="static h-11 w-11 border border-line-strong bg-transparent shadow-none"
            />
          </div>
          {bulkPrices.length > 0 ? (
            <ul className="mt-3 flex flex-wrap gap-2 text-xs text-ink-muted">
              {bulkPrices.map((price) => (
                <li key={price.id} className="rounded-full border border-line px-3 py-1">
                  {price.minQuantity}
                  <LocalizedText>+ at</LocalizedText> {formatPrice(price.priceMinor)} each
                </li>
              ))}
            </ul>
          ) : null}
          <p role="status" className="mt-2 min-h-5 text-sm text-success">
            {added ? <LocalizedText>{"Added to your basket."}</LocalizedText> : ""}
          </p>
          {preorderRequested ? (
            <p className="mt-1 rounded-sm border border-accent/30 bg-accent/5 px-3 py-2 text-sm text-ink-muted">
              <LocalizedText>
                This is a seasonal pre-order. Payment is taken now and fulfilment begins when the
                harvest arrives.
              </LocalizedText>
            </p>
          ) : null}
          {/* Either admin switch (acceptsOrders, or paymentsOverride diverging
              from the site-wide payments switch) takes priority over ordinary
              stock status in the wording: an admin turned ordering off
              deliberately, which reads differently from "we sold out and will
              restock" — but all three leave the customer with nothing to
              click, so all three get the same interest form below rather than
              a dead end. */}
          {!product.acceptsOrders || !paymentsAllowed ? (
            <p className="mt-2 text-sm text-ink-muted">
              <LocalizedText>
                We are not taking orders for this product right now. Leave your details below and we
                will let you know when it is back.
              </LocalizedText>
            </p>
          ) : variant ? (
            <AvailabilityNote availability={variant.availability} />
          ) : null}

          {purchasable && variant ? (
            <SubscribeAndSave
              variantId={variant.id}
              quantity={quantity}
              productName={product.name}
            />
          ) : null}

          <div className="mt-8 space-y-4 border-t border-line pt-6 text-sm">
            <p className="text-ink">{product.overview}</p>
            {product.harvestNote ? (
              <p className="text-ink-muted">
                <span className="font-medium text-ink">
                  <LocalizedText>Harvest:</LocalizedText>{" "}
                </span>
                {product.harvestNote}
              </p>
            ) : null}
            {product.growingMethod ? (
              <p className="text-ink-muted">
                <span className="font-medium text-ink">
                  <LocalizedText>Growing method:</LocalizedText>{" "}
                </span>
                {product.growingMethod}
              </p>
            ) : null}
            {product.storageGuidance ? (
              <p className="text-ink-muted">
                <span className="font-medium text-ink">
                  <LocalizedText>Storage:</LocalizedText>{" "}
                </span>
                {product.storageGuidance}
              </p>
            ) : null}
            <p className="text-ink-muted">
              <span className="font-medium text-ink">
                <LocalizedText>Returns:</LocalizedText>{" "}
              </span>
              {product.returnEligible ? (
                <LocalizedText>{"Eligible for return — see our returns policy."}</LocalizedText>
              ) : (
                <LocalizedText>
                  {"Not eligible for return due to the nature of this product."}
                </LocalizedText>
              )}
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
              <h2 className="font-display text-lg text-ink">
                <LocalizedText>Interested in this product?</LocalizedText>
              </h2>
              <p className="mt-1 text-sm text-ink-muted">
                <LocalizedText>We will get in touch as soon as</LocalizedText> {product.name}{" "}
                <LocalizedText>is available to order again.</LocalizedText>
              </p>
              <div className="mt-4">
                <ContactForm
                  compact
                  defaultSubject={format("Interest: {product}", { product: product.name })}
                  messagePlaceholder={format(
                    "Let us know how much {product} you would like and where it would be delivered.",
                    { product: product.name },
                  )}
                  submitLabel="Send enquiry"
                  successMessage="Thanks — we have your details and will be in touch as soon as this is back."
                />
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <Section eyebrow="Trace your food" heading="From the farm to your door" tone="subtle">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-8 lg:flex-row lg:items-start lg:justify-between">
          <ol className="grid flex-1 gap-6 sm:grid-cols-2 lg:grid-cols-5">
            {product.traceability.map((step, index) => (
              <li key={step.label} className="relative">
                <span className="font-display text-2xl text-accent">{index + 1}</span>
                {/* The API composes these from fixed English phrases, so they
                    translate through the source catalogue like any other
                    storefront copy. A detail that interpolates a farm name has
                    no catalogue entry and falls through unchanged. */}
                <p className="mt-1 font-medium text-ink">{localize(step.label)}</p>
                <p className="mt-1 text-sm text-ink-muted">{localize(step.detail)}</p>
              </li>
            ))}
          </ol>
          <ProductQrCode url={`${origin}/product/${product.slug}`} />
        </div>
      </Section>

      <div id="reviews">
        <Section
          eyebrow="Customer reviews"
          heading={format("Reviews for {product}", { product: product.name })}
          tone="subtle"
        >
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
