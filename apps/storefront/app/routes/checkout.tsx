import { formatMoney } from "@truegrit/contracts";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import type { Route } from "./+types/checkout";
import { Section } from "../components/catalogue";
import { useCart } from "../lib/cart";
import {
  commerceLive,
  getPaymentMethods,
  payWithRazorpay,
  placeOrder,
  type DeliveryAddress,
  type PaymentMethodsInfo,
} from "../lib/commerce";
import { AuthError, useCustomer } from "../lib/customer-auth";
import { seoMeta } from "../lib/seo";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Checkout",
    description: "Confirm your order.",
    canonicalPath: "/checkout",
    indexing: "noindex",
  });
}

const FREE_DELIVERY_THRESHOLD = 150000;
const DELIVERY_FEE = 4900;

const FIELD =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

export default function CheckoutPage(_props: Route.ComponentProps) {
  const { customer, status } = useCustomer();
  const { lines, subtotalMinor, clear } = useCart();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [payment, setPayment] = useState<PaymentMethodsInfo | null>(null);
  const [method, setMethod] = useState<string>("razorpay");

  const delivery =
    subtotalMinor >= FREE_DELIVERY_THRESHOLD || subtotalMinor === 0 ? 0 : DELIVERY_FEE;
  const total = subtotalMinor + delivery;

  const codAllowed =
    payment !== null && payment.methods.includes("cod") && total <= payment.codMaxMinor;
  const razorpayAllowed = payment !== null && payment.methods.includes("razorpay");

  useEffect(() => {
    if (!commerceLive) return;
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
  }, []);

  // Cart total past the COD ceiling => force online payment.
  useEffect(() => {
    if (method === "cod" && !codAllowed && razorpayAllowed) setMethod("razorpay");
  }, [method, codAllowed, razorpayAllowed]);

  if (status === "loading") {
    return (
      <Section eyebrow="Checkout" heading="One moment…">
        <p className="text-sm text-ink-muted">Checking your session.</p>
      </Section>
    );
  }

  if (status === "anonymous" || customer === null) {
    return (
      <Section eyebrow="Checkout" heading="Sign in to check out">
        <p className="max-w-md text-sm text-ink-muted">
          Use the account menu in the header to sign in with Google or your email, then return here
          to place your order. Your basket is saved.
        </p>
        <Link
          to="/cart"
          className="mt-5 inline-flex min-h-11 items-center rounded-sm border border-line px-5 text-sm font-medium text-ink hover:bg-canvas"
        >
          Back to basket
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
          Explore the market
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
    setError(null);
    setPending(true);
    try {
      const order = await placeOrder(
        lines.map((line) => ({ variantId: line.variantId, quantity: line.quantity })),
        address,
        chosen,
      );
      // Online orders open a Razorpay widget; only clear the cart once the
      // payment is verified server-side. COD orders are already confirmed.
      if (order.payment?.method === "razorpay") {
        await payWithRazorpay(order, { name: customer!.displayName, email: customer!.email });
      }
      clear();
      void navigate(`/account/orders/${order.reference}`, { replace: true });
    } catch (caught) {
      setError(caught instanceof AuthError ? caught.message : "Could not place your order.");
    } finally {
      setPending(false);
    }
  }

  return (
    <Section eyebrow="Checkout" heading="Delivery & payment">
      {!commerceLive ? (
        <p className="mb-5 rounded-sm border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
          Demo mode — set <code>VITE_API_URL</code> to place real orders.
        </p>
      ) : null}
      <form className="grid gap-10 lg:grid-cols-[1.4fr_1fr]" onSubmit={handleSubmit}>
        <div className="space-y-4">
          <h2 className="font-display text-lg text-ink">Delivery address</h2>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-ink-muted">Full name</span>
            <input
              name="recipientName"
              required
              className={FIELD}
              defaultValue={customer.displayName}
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-ink-muted">Phone (optional)</span>
            <input name="phone" className={FIELD} placeholder="+91…" />
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-ink-muted">Address line 1</span>
            <input name="line1" required className={FIELD} placeholder="House / street" />
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-ink-muted">Address line 2 (optional)</span>
            <input name="line2" className={FIELD} placeholder="Area / landmark" />
          </label>
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="block space-y-1">
              <span className="text-xs font-medium text-ink-muted">City</span>
              <input name="city" required className={FIELD} />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium text-ink-muted">State</span>
              <input name="state" required className={FIELD} />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-medium text-ink-muted">PIN code</span>
              <input name="postalCode" required className={FIELD} />
            </label>
          </div>

          {error ? (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          ) : null}
        </div>

        <aside className="h-fit rounded-md border border-line bg-surface p-5 shadow-card">
          <h2 className="font-display text-lg text-ink">Order summary</h2>
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
                  {formatMoney(line.unitMinor * line.quantity)}
                </span>
              </li>
            ))}
          </ul>
          <dl className="mt-3 space-y-1.5 border-t border-line pt-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-muted">Subtotal</dt>
              <dd className="text-ink">{formatMoney(subtotalMinor)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-muted">Delivery</dt>
              <dd className="text-ink">{delivery === 0 ? "Free" : formatMoney(delivery)}</dd>
            </div>
            <div className="flex justify-between border-t border-line pt-1.5 font-medium">
              <dt>Total</dt>
              <dd>{formatMoney(total)}</dd>
            </div>
          </dl>
          <fieldset className="mt-4 space-y-2">
            <legend className="text-xs font-medium text-ink-muted">Payment method</legend>
            {razorpayAllowed ? (
              <label className="flex cursor-pointer items-start gap-2 rounded-sm border border-line px-3 py-2 text-sm">
                <input
                  type="radio"
                  name="paymentMethod"
                  className="mt-0.5"
                  checked={method === "razorpay"}
                  onChange={() => setMethod("razorpay")}
                />
                <span className="text-ink">Pay online — UPI, cards, netbanking &amp; wallets</span>
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
                Cash on delivery
                {payment && !codAllowed ? (
                  <span className="mt-0.5 block text-xs text-ink-muted">
                    Available only up to {formatMoney(payment.codMaxMinor)} and when you have no
                    other unpaid COD order.
                  </span>
                ) : null}
              </span>
            </label>
          </fieldset>
          <p className="mt-2 text-xs text-ink-muted">
            Prices are re-validated server-side before your order is confirmed.
          </p>
          <button
            type="submit"
            disabled={pending}
            className="mt-4 min-h-11 w-full rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-95 disabled:opacity-60"
          >
            {pending ? "Processing…" : method === "cod" ? "Place order" : "Pay & place order"}
          </button>
        </aside>
      </form>
    </Section>
  );
}
