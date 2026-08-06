import { formatMoney } from "@truegrit/contracts";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import type { Route } from "./+types/checkout";
import { Section } from "../components/catalogue";
import { ContactForm } from "../components/contact-form";
import { PromotionBanner } from "../components/promotion-banner";
import { useCart } from "../lib/cart";
import {
  commerceLive,
  getDeliverySettings,
  getFeaturedPromotion,
  getPaymentMethods,
  newCheckoutIdempotencyKey,
  openPaypalPaymentWindow,
  openRazorpayPaymentWindow,
  payWithPaypalWindow,
  payWithRazorpayWindow,
  placeOrder,
  previewDiscount,
  previewGiftCard,
  type DeliveryAddress,
  type DeliverySettingsInfo,
  type DiscountPreview,
  type FeaturedPromotionInfo,
  type GiftCardPreview,
  type PaymentMethodsInfo,
} from "../lib/commerce";
import { usePriceFormatter, useDisplayCurrency } from "../lib/currency";
import { AuthError, useCustomer } from "../lib/customer-auth";
import { seoMeta } from "../lib/seo";
import { useSiteSettings } from "../lib/site-settings";
import { LocalizedText, useLocalizeText } from "../lib/i18n/localized-text";

export function meta({ matches }: Route.MetaArgs) {
  return seoMeta(
    {
      title: "Checkout",
      description: "Confirm your order.",
      canonicalPath: "/checkout",
      indexing: "noindex",
    },
    matches,
  );
}

// Shown until `getDeliverySettings` resolves -- matches the API's own shipped
// default (`DEFAULT_DELIVERY_FEE_MINOR` / `DEFAULT_FREE_DELIVERY_THRESHOLD_MINOR`
// in `feature_settings.py`), so an owner who has not changed it never sees a
// flash of the wrong figure, and one who has still gets the true value the
// moment the fetch lands.
const DEFAULT_DELIVERY_SETTINGS: DeliverySettingsInfo = {
  feeMinor: 4900,
  freeThresholdMinor: 150000,
};

const FIELD =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

export default function CheckoutPage(_props: Route.ComponentProps) {
  const localize = useLocalizeText();
  const { customer, status } = useCustomer();
  const { payments, promotions, giftCards } = useSiteSettings();
  const { lines, subtotalMinor, clear } = useCart();
  const formatPrice = usePriceFormatter();
  const displayCurrency = useDisplayCurrency();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [payment, setPayment] = useState<PaymentMethodsInfo | null>(null);
  const [method, setMethod] = useState<string>("razorpay");
  const [deliverySettings, setDeliverySettings] = useState(DEFAULT_DELIVERY_SETTINGS);
  const [featuredPromotion, setFeaturedPromotion] = useState<FeaturedPromotionInfo | null>(null);
  const [couponInput, setCouponInput] = useState("");
  const [appliedDiscount, setAppliedDiscount] = useState<DiscountPreview | null>(null);
  const [couponChecking, setCouponChecking] = useState(false);
  const [couponError, setCouponError] = useState<string | null>(null);
  const [giftCardInput, setGiftCardInput] = useState("");
  const [appliedGiftCard, setAppliedGiftCard] = useState<GiftCardPreview | null>(null);
  const [giftCardChecking, setGiftCardChecking] = useState(false);
  const [giftCardError, setGiftCardError] = useState<string | null>(null);
  // Stable for the life of this page: every retry of the same submission
  // (a double-click, a timeout-and-resend) reuses it, so the server returns
  // the order that attempt already placed instead of placing a second one.
  const [idempotencyKey] = useState(newCheckoutIdempotencyKey);

  const baseDelivery =
    subtotalMinor >= deliverySettings.freeThresholdMinor || subtotalMinor === 0
      ? 0
      : deliverySettings.feeMinor;
  // A confirmed preview from `previewDiscount`, not merely a typed code — the
  // total shown here must never promise a discount the server has not itself
  // verified. Submitting still sends whatever code is in the box either way
  // (see `handleSubmit`); the API is the final authority regardless of
  // whether this preview ran.
  const discount = appliedDiscount?.discountMinor ?? 0;
  const delivery = appliedDiscount?.freeDelivery ? 0 : baseDelivery;
  const preGiftCardTotal = Math.max(subtotalMinor + delivery - discount, 0);
  // Same "confirmed preview, server is the final authority" rule as the
  // coupon discount above -- see the comment there.
  const giftCardApplied = appliedGiftCard?.appliedMinor ?? 0;
  const total = Math.max(preGiftCardTotal - giftCardApplied, 0);

  const codAllowed =
    payment !== null && payment.methods.includes("cod") && total <= payment.codMaxMinor;
  const razorpayAllowed = payment !== null && payment.methods.includes("razorpay");
  const paypalAllowed = payment !== null && payment.methods.includes("paypal");

  useEffect(() => {
    if (!commerceLive || !payments.enabled) return;
    let active = true;
    getPaymentMethods()
      .then((info) => {
        if (!active) return;
        setPayment(info);
        setMethod(info.methods.includes("razorpay") ? "razorpay" : "cod");
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [payments.enabled]);

  useEffect(() => {
    if (!commerceLive || !payments.enabled) return;
    let active = true;
    getDeliverySettings()
      .then((info) => {
        if (active) setDeliverySettings(info);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [payments.enabled]);

  useEffect(() => {
    if (!commerceLive || !payments.enabled || !promotions.enabled) return;
    let active = true;
    getFeaturedPromotion()
      .then((info) => {
        if (active) setFeaturedPromotion(info);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [payments.enabled, promotions.enabled]);

  // A discount preview is only true for the basket it was computed against —
  // a quantity change afterwards invalidates it rather than silently keeping
  // a stale figure on screen.
  useEffect(() => {
    setAppliedDiscount(null);
    setCouponError(null);
  }, [subtotalMinor]);

  // A gift card preview is only true for the amount it was computed against
  // -- a quantity change or a coupon being applied/removed changes what is
  // left to cover, so the stale preview is dropped rather than kept on
  // screen.
  useEffect(() => {
    setAppliedGiftCard(null);
    setGiftCardError(null);
  }, [subtotalMinor, discount, delivery]);

  // Cart total past the COD ceiling => force online payment.
  useEffect(() => {
    if (method === "cod" && !codAllowed && razorpayAllowed) setMethod("razorpay");
  }, [method, codAllowed, razorpayAllowed]);

  async function handleApplyCoupon() {
    const code = couponInput.trim();
    if (!code) return;
    setCouponChecking(true);
    setCouponError(null);
    try {
      const result = await previewDiscount(code, subtotalMinor);
      setAppliedDiscount(result);
    } catch (caught) {
      setAppliedDiscount(null);
      setCouponError(caught instanceof AuthError ? caught.message : "Could not apply this code.");
    } finally {
      setCouponChecking(false);
    }
  }

  async function handleApplyGiftCard() {
    const code = giftCardInput.trim();
    if (!code) return;
    setGiftCardChecking(true);
    setGiftCardError(null);
    try {
      const result = await previewGiftCard(code, preGiftCardTotal);
      setAppliedGiftCard(result);
    } catch (caught) {
      setAppliedGiftCard(null);
      setGiftCardError(
        caught instanceof AuthError ? caught.message : "Could not apply this gift card.",
      );
    } finally {
      setGiftCardChecking(false);
    }
  }

  // Ordering switched off in the admin console. This is checked before the
  // session and the basket: whether they are signed in or how full the basket
  // is changes nothing, and the API refuses this checkout either way. Rather
  // than a dead end, take their details so the interest is not lost.
  if (!payments.enabled) {
    return (
      <Section eyebrow="Checkout" heading="Ordering is paused">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="max-w-2xl space-y-5">
            <p className="text-base text-ink-muted">{payments.disabledNotice}</p>
            <ContactForm
              defaultSubject="Order enquiry"
              messagePlaceholder="Tell us what you were hoping to order and where it would be delivered."
              submitLabel="Send enquiry"
              successMessage="Thanks — we have your details and will be in touch as soon as ordering reopens."
            />
          </div>
          <aside className="space-y-5">
            <div>
              <h2 className="font-display text-lg text-ink">
                <LocalizedText>Your basket is safe</LocalizedText>
              </h2>
              <p className="mt-2 text-sm text-ink-muted">
                <LocalizedText>
                  Nothing has been cleared. When ordering reopens, everything you picked will still
                  be here.
                </LocalizedText>
              </p>
              <Link
                to="/cart"
                className="mt-4 inline-flex min-h-11 items-center rounded-sm border border-line px-5 text-sm font-medium text-ink hover:bg-canvas"
              >
                <LocalizedText>Back to basket</LocalizedText>
              </Link>
            </div>
            <div>
              <h2 className="font-display text-lg text-ink">
                <LocalizedText>Prefer email?</LocalizedText>
              </h2>
              <a
                href="mailto:support@truegrit.test"
                className="mt-2 block text-sm text-brand underline-offset-4 hover:underline"
              >
                <LocalizedText>support@truegrit.test</LocalizedText>
              </a>
            </div>
          </aside>
        </div>
      </Section>
    );
  }

  if (status === "loading") {
    return (
      <Section eyebrow="Checkout" heading="One moment…">
        <p className="text-sm text-ink-muted">
          <LocalizedText>Checking your session.</LocalizedText>
        </p>
      </Section>
    );
  }

  if (status === "anonymous" || customer === null) {
    return (
      <Section eyebrow="Checkout" heading="Sign in to check out">
        <p className="max-w-md text-sm text-ink-muted">
          <LocalizedText>
            Use the account menu in the header to sign in with Google or your email, then return
            here to place your order. Your basket is saved.
          </LocalizedText>
        </p>
        <Link
          to="/cart"
          className="mt-5 inline-flex min-h-11 items-center rounded-sm border border-line px-5 text-sm font-medium text-ink hover:bg-canvas"
        >
          <LocalizedText>Back to basket</LocalizedText>
        </Link>
      </Section>
    );
  }

  if (lines.length === 0) {
    return (
      <Section eyebrow="Checkout" heading="Your basket is empty">
        <Link
          to="/shop"
          className="mt-2 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
        >
          <LocalizedText>Explore the market</LocalizedText>
        </Link>
      </Section>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const address: DeliveryAddress = {
      recipientName: String(form.get("recipientName") ?? ""),
      phoneE164: String(form.get("phone") ?? "") || undefined,
      line1: String(form.get("line1") ?? ""),
      line2: String(form.get("line2") ?? "") || undefined,
      city: String(form.get("city") ?? ""),
      state: String(form.get("state") ?? ""),
      postalCode: String(form.get("postalCode") ?? ""),
    };
    const chosen = method === "cod" && !codAllowed ? "razorpay" : method;
    // Open the popup synchronously, before any await: a window opened after an
    // async hop is no longer tied to the click and browsers block it.
    const paymentWindow =
      chosen === "razorpay"
        ? openRazorpayPaymentWindow()
        : chosen === "paypal"
          ? openPaypalPaymentWindow()
          : null;
    setError(null);
    setPending(true);
    try {
      const order = await placeOrder(
        lines.map((line) => ({ variantId: line.variantId, quantity: line.quantity })),
        address,
        chosen,
        idempotencyKey,
        couponInput.trim() || undefined,
        giftCardInput.trim() || undefined,
      );
      // Online orders open a gateway window; only clear the cart once the
      // payment is settled server-side. COD orders are already confirmed.
      if (order.payment?.method === "razorpay") {
        await payWithRazorpayWindow(
          order,
          {
            name: customer!.displayName,
            email: customer!.email ?? undefined,
            contact: customer!.phone ?? address.phoneE164,
          },
          paymentWindow,
        );
      } else if (order.payment?.method === "paypal") {
        // No prefill: PayPal authenticates the buyer in its own window, and the
        // account paying may not be the account shopping (someone abroad paying
        // for a delivery here).
        await payWithPaypalWindow(order, paymentWindow);
      }
      clear();
      void navigate(`/account/orders/${order.reference}`, { replace: true });
    } catch (caught) {
      if (paymentWindow && !paymentWindow.closed) paymentWindow.close();
      setError(caught instanceof AuthError ? caught.message : "Could not place your order.");
    } finally {
      setPending(false);
    }
  }

  return (
    <Section eyebrow="Checkout" heading="Delivery & payment">
      {!commerceLive ? (
        <p className="mb-5 rounded-sm border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
          <LocalizedText>Demo mode — set</LocalizedText> <code>VITE_API_URL</code>{" "}
          <LocalizedText>to place real orders.</LocalizedText>
        </p>
      ) : null}
      <form className="grid gap-10 lg:grid-cols-[1.4fr_1fr]" onSubmit={handleSubmit}>
        <div className="space-y-4">
          <h2 className="font-display text-lg text-ink">
            <LocalizedText>Delivery address</LocalizedText>
          </h2>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-ink-muted">
              <LocalizedText>Full name</LocalizedText>
            </span>
            <input
              name="recipientName"
              required
              className={FIELD}
              defaultValue={customer.displayName}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-ink-muted">
              <LocalizedText>Phone (optional)</LocalizedText>
            </span>
            <input name="phone" className={FIELD} placeholder="+91…" />
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-ink-muted">
              <LocalizedText>Address line 1</LocalizedText>
            </span>
            <input
              name="line1"
              required
              className={FIELD}
              placeholder={localize("House / street")}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-ink-muted">
              <LocalizedText>Address line 2 (optional)</LocalizedText>
            </span>
            <input name="line2" className={FIELD} placeholder={localize("Area / landmark")} />
          </label>
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="block space-y-1">
              <span className="text-xs font-medium text-ink-muted">
                <LocalizedText>City</LocalizedText>
              </span>
              <input name="city" required className={FIELD} />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium text-ink-muted">
                <LocalizedText>State</LocalizedText>
              </span>
              <input name="state" required className={FIELD} />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium text-ink-muted">
                <LocalizedText>PIN code</LocalizedText>
              </span>
              <input name="postalCode" required className={FIELD} />
            </label>
          </div>

          {error ? (
            <p role="alert" className="text-sm text-danger">
              {localize(error)}
            </p>
          ) : null}
        </div>

        <aside className="h-fit rounded-md border border-line bg-surface p-5 shadow-card">
          <h2 className="font-display text-lg text-ink">
            <LocalizedText>Order summary</LocalizedText>
          </h2>
          <ul className="mt-3 divide-y divide-line text-sm">
            {lines.map((line) => (
              <li key={line.variantId} className="flex justify-between gap-3 py-2">
                <span className="min-w-0">
                  <span className="block truncate text-ink">{line.productName}</span>
                  <span className="text-xs text-ink-muted">
                    {line.variantName} × {line.quantity}
                  </span>
                </span>
                <span className="whitespace-nowrap text-ink">
                  {formatPrice(line.unitMinor * line.quantity)}
                </span>
              </li>
            ))}
          </ul>

          {promotions.enabled && commerceLive ? (
            <div className="mt-3">
              {featuredPromotion ? (
                <PromotionBanner promotion={featuredPromotion} variant="compact" />
              ) : null}
              <div className="mt-3">
                <label htmlFor="couponCode" className="text-xs font-medium text-ink-muted">
                  <LocalizedText>Coupon code</LocalizedText>
                </label>
                <div className="mt-1 flex gap-2">
                  <input
                    id="couponCode"
                    className={`${FIELD} min-h-9`}
                    placeholder={localize("e.g. WELCOME15")}
                    value={couponInput}
                    onChange={(event) => {
                      setCouponInput(event.target.value);
                      setAppliedDiscount(null);
                      setCouponError(null);
                    }}
                  />
                  <button
                    type="button"
                    disabled={!couponInput.trim() || couponChecking}
                    onClick={() => void handleApplyCoupon()}
                    className="min-h-9 shrink-0 rounded-sm border border-line px-3 text-sm font-medium text-ink hover:bg-canvas disabled:opacity-60"
                  >
                    {couponChecking ? (
                      <LocalizedText>{"Checking…"}</LocalizedText>
                    ) : (
                      <LocalizedText>{"Apply"}</LocalizedText>
                    )}
                  </button>
                </div>
                {couponError ? (
                  <p className="mt-1 text-xs text-danger">{localize(couponError)}</p>
                ) : null}
                {appliedDiscount ? (
                  <p className="mt-1 text-xs text-success">
                    "{appliedDiscount.code}
                    <LocalizedText>" applied —</LocalizedText> {appliedDiscount.headline}
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}

          {giftCards.enabled && commerceLive ? (
            <div className="mt-3">
              <label htmlFor="giftCardCode" className="text-xs font-medium text-ink-muted">
                <LocalizedText>Gift card code</LocalizedText>
              </label>
              <div className="mt-1 flex gap-2">
                <input
                  id="giftCardCode"
                  className={`${FIELD} min-h-9`}
                  placeholder={localize("e.g. DIWALI500")}
                  value={giftCardInput}
                  onChange={(event) => {
                    setGiftCardInput(event.target.value);
                    setAppliedGiftCard(null);
                    setGiftCardError(null);
                  }}
                />
                <button
                  type="button"
                  disabled={!giftCardInput.trim() || giftCardChecking}
                  onClick={() => void handleApplyGiftCard()}
                  className="min-h-9 shrink-0 rounded-sm border border-line px-3 text-sm font-medium text-ink hover:bg-canvas disabled:opacity-60"
                >
                  {giftCardChecking ? (
                    <LocalizedText>{"Checking…"}</LocalizedText>
                  ) : (
                    <LocalizedText>{"Apply"}</LocalizedText>
                  )}
                </button>
              </div>
              {giftCardError ? (
                <p className="mt-1 text-xs text-danger">{localize(giftCardError)}</p>
              ) : null}
              {appliedGiftCard ? (
                <p className="mt-1 text-xs text-success">
                  "{appliedGiftCard.code}
                  <LocalizedText>" applied —</LocalizedText>{" "}
                  {formatPrice(appliedGiftCard.appliedMinor)}{" "}
                  <LocalizedText>toward this order</LocalizedText>
                  {appliedGiftCard.remainingAfterMinor > 0 ? (
                    <>
                      , {formatPrice(appliedGiftCard.remainingAfterMinor)}{" "}
                      <LocalizedText>left on the card</LocalizedText>
                    </>
                  ) : null}
                </p>
              ) : null}
            </div>
          ) : null}

          <dl className="mt-3 space-y-1.5 border-t border-line pt-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-muted">
                <LocalizedText>Subtotal</LocalizedText>
              </dt>
              <dd className="text-ink">{formatPrice(subtotalMinor)}</dd>
            </div>
            {discount > 0 ? (
              <div className="flex justify-between">
                <dt className="text-ink-muted">
                  <LocalizedText>Discount</LocalizedText>
                </dt>
                <dd className="text-success">−{formatPrice(discount)}</dd>
              </div>
            ) : null}
            <div className="flex justify-between">
              <dt className="text-ink-muted">
                <LocalizedText>Delivery</LocalizedText>
              </dt>
              <dd className="text-ink">
                {delivery === 0 ? <LocalizedText>{"Free"}</LocalizedText> : formatPrice(delivery)}
              </dd>
            </div>
            {giftCardApplied > 0 ? (
              <div className="flex justify-between">
                <dt className="text-ink-muted">
                  <LocalizedText>Gift card</LocalizedText>
                </dt>
                <dd className="text-success">−{formatPrice(giftCardApplied)}</dd>
              </div>
            ) : null}
            <div className="flex justify-between border-t border-line pt-1.5 font-medium">
              <dt>
                <LocalizedText>Total</LocalizedText>
              </dt>
              <dd>{formatPrice(total)}</dd>
            </div>
          </dl>
          {displayCurrency.code !== "INR" ? (
            <p className="mt-2 text-xs text-ink-muted">
              <LocalizedText>Prices shown in</LocalizedText> {displayCurrency.code}{" "}
              <LocalizedText>are approximate. Your payment is charged as</LocalizedText>{" "}
              {formatMoney(total)}.
            </p>
          ) : null}
          <fieldset className="mt-4 space-y-2">
            <legend className="text-xs font-medium text-ink-muted">
              <LocalizedText>Payment method</LocalizedText>
            </legend>
            {razorpayAllowed ? (
              <label className="flex cursor-pointer items-start gap-2 rounded-sm border border-line px-3 py-2 text-sm">
                <input
                  type="radio"
                  name="paymentMethod"
                  className="mt-0.5"
                  checked={method === "razorpay"}
                  onChange={() => setMethod("razorpay")}
                />
                <span className="text-ink">
                  <LocalizedText>Pay online — UPI, cards, netbanking &amp; wallets</LocalizedText>
                </span>
              </label>
            ) : null}
            {paypalAllowed ? (
              <label className="flex cursor-pointer items-start gap-2 rounded-sm border border-line px-3 py-2 text-sm">
                <input
                  type="radio"
                  name="paymentMethod"
                  className="mt-0.5"
                  checked={method === "paypal"}
                  onChange={() => setMethod("paypal")}
                />
                <span className="text-ink">
                  <LocalizedText>PayPal — for international cards</LocalizedText>
                  {/* PayPal cannot settle INR to an Indian merchant, so this is
                      the overseas lane only. Say who it is for, so domestic
                      customers do not pick it and hit a conversion they did not
                      want. */}
                  <span className="mt-0.5 block text-xs text-ink-muted">
                    <LocalizedText>Paying from outside India? Charged in</LocalizedText>{" "}
                    {payment?.paypalCurrency || <LocalizedText>{"USD"}</LocalizedText>}{" "}
                    <LocalizedText>at today's rate.</LocalizedText>
                  </span>
                </span>
              </label>
            ) : null}
            <label
              className={`flex items-start gap-2 rounded-sm border border-line px-3 py-2 text-sm ${
                codAllowed ? "cursor-pointer" : "opacity-60"
              }`}
            >
              <input
                type="radio"
                name="paymentMethod"
                className="mt-0.5"
                checked={method === "cod"}
                disabled={!codAllowed}
                onChange={() => setMethod("cod")}
              />
              <span className="text-ink">
                <LocalizedText>Cash on delivery</LocalizedText>
                {payment && !codAllowed ? (
                  <span className="mt-0.5 block text-xs text-ink-muted">
                    <LocalizedText>Available only up to</LocalizedText>{" "}
                    {formatMoney(payment.codMaxMinor)}{" "}
                    <LocalizedText>and when you have no other unpaid COD order.</LocalizedText>
                  </span>
                ) : null}
              </span>
            </label>
          </fieldset>
          <p className="mt-2 text-xs text-ink-muted">
            <LocalizedText>
              Prices are re-validated server-side before your order is confirmed.
            </LocalizedText>
          </p>
          <button
            type="submit"
            disabled={pending}
            className="mt-4 min-h-11 w-full rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-95 disabled:opacity-60"
          >
            {pending ? (
              <LocalizedText>{"Processing…"}</LocalizedText>
            ) : method === "cod" ? (
              <LocalizedText>{"Place order"}</LocalizedText>
            ) : (
              <LocalizedText>{"Pay & place order"}</LocalizedText>
            )}
          </button>
        </aside>
      </form>
    </Section>
  );
}
