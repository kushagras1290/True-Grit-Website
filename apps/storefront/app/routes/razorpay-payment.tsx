import { CheckCircle2, Loader2, LockKeyhole, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import type { Route } from "./+types/razorpay-payment";
import { payWithRazorpay, readRazorpayWindowPayload, type PlacedOrder } from "../lib/commerce";
import { AuthError } from "../lib/customer-auth";
import { seoMeta } from "../lib/seo";
import { LocalizedText, useLocalizeText } from "../lib/i18n/localized-text";

type PaymentState = "preparing" | "processing" | "paid" | "failed";

export function meta({ matches }: Route.MetaArgs) {
  return seoMeta(
    {
      title: "Razorpay payment",
      description: "Complete your True Grit payment.",
      canonicalPath: "/payment/razorpay",
      indexing: "noindex",
    },
    matches,
  );
}

function notifyOpener(
  token: string,
  status: "paid" | "failed" | "cancelled",
  payload: { order?: PlacedOrder & { ok: boolean }; message?: string } = {},
) {
  if (typeof window === "undefined" || !window.opener) return;
  window.opener.postMessage(
    {
      source: "truegrit:razorpay",
      token,
      status,
      ...payload,
    },
    window.location.origin,
  );
}

export default function RazorpayPaymentPage(_props: Route.ComponentProps) {
  const localize = useLocalizeText();
  const [params] = useSearchParams();
  const token = params.get("token");
  const status = params.get("status");
  const started = useRef(false);
  const [state, setState] = useState<PaymentState>("preparing");
  const [message, setMessage] = useState("Preparing your secure payment window.");
  const [reference, setReference] = useState<string | null>(null);

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

    started.current = true;
    const payload = readRazorpayWindowPayload(token);
    if (!payload) {
      setState("failed");
      setMessage("This payment session has expired. Please return to checkout.");
      notifyOpener(token, "failed", {
        message: "The payment session expired before Razorpay could open.",
      });
      return;
    }

    setReference(payload.order.reference);
    setState("processing");
    setMessage("Razorpay is opening for this order.");

    payWithRazorpay(payload.order, payload.prefill)
      .then((paidOrder) => {
        setState("paid");
        setMessage("Payment verified. Returning to your order.");
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
          {
            message: text,
          },
        );
      });
  }, [status, token]);

  const isBusy = state === "preparing" || state === "processing";
  const Icon = state === "paid" ? CheckCircle2 : state === "failed" ? XCircle : Loader2;

  return (
    <div className="min-h-screen bg-canvas">
      <div className="mx-auto flex min-h-screen w-full max-w-[34rem] flex-col px-5 py-6">
        <header className="flex items-center justify-between border-b border-line pb-4">
          <Link to="/" className="font-display text-xl text-ink">
            True Grit
          </Link>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1 text-xs font-medium text-ink-muted">
            <LockKeyhole className="h-3.5 w-3.5" aria-hidden />
            <LocalizedText>Razorpay</LocalizedText>
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
              <LocalizedText>Secure payment</LocalizedText>
            </p>
            <h1 className="mt-2 font-display text-3xl leading-tight text-ink">
              {state === "paid" ? (
                <LocalizedText>{"Payment complete"}</LocalizedText>
              ) : state === "failed" ? (
                <LocalizedText>{"Payment needs attention"}</LocalizedText>
              ) : (
                <LocalizedText>{"Opening Razorpay"}</LocalizedText>
              )}
            </h1>
            <p className="mt-3 text-sm leading-6 text-ink-muted">{localize(message)}</p>
            {reference ? (
              <p className="mt-5 rounded-sm border border-line bg-canvas px-3 py-2 text-sm text-ink">
                <LocalizedText>Order</LocalizedText>{" "}
                <span className="font-medium">{reference}</span>
              </p>
            ) : null}
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
            Payments are processed by Razorpay. True Grit never stores card details.
          </LocalizedText>
        </footer>
      </div>
    </div>
  );
}
