import { CheckCircle2, Globe2, Loader2, LockKeyhole, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import type { Route } from "./+types/paypal-payment";
import { payWithPaypal, readPaypalWindowPayload, type PlacedOrder } from "../lib/commerce";
import { AuthError } from "../lib/customer-auth";
import { seoMeta } from "../lib/seo";
import { LocalizedText, useLocalizeText } from "../lib/i18n/localized-text";

type PaymentState = "preparing" | "processing" | "paid" | "failed";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "PayPal payment",
    description: "Complete your True Grit payment.",
    canonicalPath: "/payment/paypal",
    indexing: "noindex",
  });
}

function notifyOpener(
  token: string,
  status: "paid" | "failed" | "cancelled",
  payload: { order?: PlacedOrder & { ok: boolean }; message?: string } = {},
) {
  if (typeof window === "undefined" || !window.opener) return;
  window.opener.postMessage(
    { source: "truegrit:paypal", token, status, ...payload },
    window.location.origin,
  );
}

/** Format the converted charge, e.g. 1077 + "USD" -> "$10.77". Falls back to the
 *  ISO code for currencies the runtime has no symbol for. */
function formatCharge(minor: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(minor / 100);
  } catch {
    return `${(minor / 100).toFixed(2)} ${currency}`;
  }
}

export default function PaypalPaymentPage(_props: Route.ComponentProps) {
  const localize = useLocalizeText();
  const [params] = useSearchParams();
  const token = params.get("token");
  const status = params.get("status");
  const started = useRef(false);
  const buttonsRef = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<PaymentState>("preparing");
  const [message, setMessage] = useState("Preparing your secure payment window.");
  const [order, setOrder] = useState<PlacedOrder | null>(null);

  useEffect(() => {
    if (started.current) return;
    if (status === "starting") {
      setState("preparing");
      setMessage("Preparing your order with the store.");
      return;
    }
    if (!token) {
      setState("failed");
      setMessage("This payment window is missing its checkout session.");
      return;
    }

    const payload = readPaypalWindowPayload(token);
    if (!payload) {
      setState("failed");
      setMessage("This payment session has expired. Please return to checkout.");
      notifyOpener(token, "failed", {
        message: "The payment session expired before PayPal could open.",
      });
      return;
    }

    setOrder(payload.order);
    setState("processing");
    setMessage("Choose how you'd like to pay.");
  }, [status, token]);

  // Render the buttons only once the container exists — PayPal's SDK mounts into
  // a live node, so this cannot run in the effect above where `order` is still
  // null and the element is unmounted.
  useEffect(() => {
    if (!order || !token || started.current || !buttonsRef.current) return;
    started.current = true;

    payWithPaypal(order, buttonsRef.current)
      .then((paidOrder) => {
        setState("paid");
        setMessage("Payment confirmed. Returning to your order.");
        notifyOpener(token, "paid", { order: paidOrder });
        window.setTimeout(() => window.close(), 1200);
      })
      .catch((caught) => {
        const text =
          caught instanceof AuthError
            ? caught.message
            : "Payment could not be completed. Please return to checkout.";
        setState("failed");
        setMessage(text);
        notifyOpener(
          token,
          caught instanceof AuthError && caught.code === "cancelled" ? "cancelled" : "failed",
          { message: text },
        );
      });
  }, [order, token]);

  const isBusy = state === "preparing";
  const Icon = state === "paid" ? CheckCircle2 : state === "failed" ? XCircle : Loader2;
  const charge =
    order?.payment?.amountMinor && order.payment.currency
      ? formatCharge(order.payment.amountMinor, order.payment.currency)
      : null;

  return (
    <div className="min-h-screen bg-canvas">
      <div className="mx-auto flex min-h-screen w-full max-w-[34rem] flex-col px-5 py-6">
        <header className="flex items-center justify-between border-b border-line pb-4">
          <Link to="/" className="font-display text-xl text-ink">
            True Grit
          </Link>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1 text-xs font-medium text-ink-muted">
            <LockKeyhole className="h-3.5 w-3.5" aria-hidden />
            <LocalizedText>PayPal</LocalizedText>
          </span>
        </header>

        <main className="flex flex-1 items-center py-10">
          <section className="w-full rounded-md border border-line bg-surface p-6 shadow-card sm:p-8">
            <div
              className={`mb-5 inline-flex h-12 w-12 items-center justify-center rounded-full ${
                state === "paid"
                  ? "bg-success/10 text-success"
                  : state === "failed"
                    ? "bg-danger/10 text-danger"
                    : "bg-brand/10 text-brand"
              }`}
            >
              <Icon className={`h-6 w-6 ${isBusy ? "animate-spin" : ""}`} aria-hidden />
            </div>
            <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
              <LocalizedText>Secure international payment</LocalizedText>
            </p>
            <h1 className="mt-2 font-display text-3xl leading-tight text-ink">
              {state === "paid"
                ? "Payment complete"
                : state === "failed"
                  ? "Payment needs attention"
                  : "Pay with PayPal"}
            </h1>
            <p className="mt-3 text-sm leading-6 text-ink-muted">{message}</p>

            {order ? (
              <div className="mt-5 space-y-2 rounded-sm border border-line bg-canvas px-3 py-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-ink-muted">
                    <LocalizedText>Order</LocalizedText>
                  </span>
                  <span className="font-medium text-ink">{order.reference}</span>
                </div>
                {charge ? (
                  <div className="flex items-center justify-between">
                    <span className="text-ink-muted">
                      <LocalizedText>You'll be charged</LocalizedText>
                    </span>
                    <span className="font-medium text-ink">{charge}</span>
                  </div>
                ) : null}
              </div>
            ) : null}

            {charge ? (
              <p className="mt-3 flex items-start gap-1.5 text-xs leading-5 text-ink-muted">
                <Globe2 className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                {/* PayPal cannot settle INR to an Indian merchant, so the buyer
                    is charged a converted amount. Say so before they pay rather
                    than surprise them on their statement. */}
                <LocalizedText>
                  PayPal is for international cards. Your order is priced in rupees and converted
                  for this payment, so your statement will show
                </LocalizedText>{" "}
                {charge}.
              </p>
            ) : null}

            {/* The SDK mounts here. Kept in the tree while processing so the
                container exists when the effect above runs. */}
            <div
              ref={buttonsRef}
              className={`mt-5 ${state === "processing" ? "" : "hidden"}`}
              aria-label={localize("PayPal payment options")}
            />

            {state === "failed" ? (
              <button
                type="button"
                onClick={() => window.close()}
                className="mt-6 min-h-11 w-full rounded-sm border border-line-strong px-4 text-sm font-medium text-ink hover:bg-canvas"
              >
                <LocalizedText>Close window</LocalizedText>
              </button>
            ) : null}
          </section>
        </main>

        <footer className="border-t border-line pt-4 text-center text-xs text-ink-muted">
          <LocalizedText>
            Payments are processed by PayPal. True Grit never stores card details.
          </LocalizedText>
        </footer>
      </div>
    </div>
  );
}
