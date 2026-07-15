import { formatMoney } from "@truegrit/contracts";
import { Ban, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import type { Route } from "./+types/order";
import { Section } from "../components/catalogue";
import { getMyOrder, type OrderDetail } from "../lib/commerce";
import { useCustomer } from "../lib/customer-auth";
import { seoMeta } from "../lib/seo";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Track your order",
    description: "Order details and delivery progress.",
    canonicalPath: "/account",
    indexing: "noindex",
  });
}

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "loaded"; order: OrderDetail };

const TRACK_STEPS = [
  { label: "Order placed", description: "We've received your order." },
  { label: "Confirmed", description: "Payment settled and order accepted." },
  { label: "Processing", description: "Being picked and packed at the farm hub." },
  { label: "Out for delivery", description: "On its way to your address." },
  { label: "Delivered", description: "Enjoy your order." },
] as const;

/** Map the order's statuses to the furthest reached tracking step (0-4), or -1
 *  when the order was cancelled. */
function currentStep(order: OrderDetail): number {
  if (order.orderStatus === "cancelled") return -1;
  if (order.orderStatus === "completed" || order.fulfilmentStatus === "fulfilled") return 4;
  if (order.fulfilmentStatus === "shipped" || order.fulfilmentStatus === "out_for_delivery")
    return 3;
  if (order.orderStatus === "processing" || order.fulfilmentStatus === "processing") return 2;
  if (order.orderStatus === "confirmed") return 1;
  return 0;
}

function TrackingTimeline({ order }: { order: OrderDetail }) {
  const step = currentStep(order);

  if (step === -1) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-ink">
        <Ban size={18} className="text-danger" aria-hidden />
        <span>This order was cancelled.</span>
      </div>
    );
  }

  return (
    <ol className="rounded-md border border-line bg-surface p-5">
      {TRACK_STEPS.map((item, index) => {
        const done = index < step;
        const current = index === step;
        return (
          <li key={item.label} className="flex gap-3 pb-5 last:pb-0">
            <div className="flex flex-col items-center">
              {done ? (
                <CheckCircle2 size={20} className="text-brand" aria-hidden />
              ) : current ? (
                <Loader2 size={20} className="animate-spin text-brand" aria-hidden />
              ) : (
                <Circle size={20} className="text-line" aria-hidden />
              )}
              {index < TRACK_STEPS.length - 1 ? (
                <span
                  className={`mt-1 w-px flex-1 ${index < step ? "bg-brand" : "bg-line"}`}
                  aria-hidden
                />
              ) : null}
            </div>
            <div className="pb-1">
              <p
                className={`text-sm font-medium ${
                  done || current ? "text-ink" : "text-ink-muted"
                }`}
              >
                {item.label}
                {current ? (
                  <span className="ml-2 rounded-full bg-subtle px-2 py-0.5 text-[11px] text-brand">
                    In progress
                  </span>
                ) : null}
              </p>
              <p className="text-xs text-ink-muted">{item.description}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export default function OrderPage(_props: Route.ComponentProps) {
  const { reference = "" } = useParams();
  const { status } = useCustomer();
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    if (status !== "authenticated") return;
    let active = true;
    getMyOrder(reference)
      .then((order) => active && setState({ kind: "loaded", order }))
      .catch(() =>
        active ? setState({ kind: "error", message: "We couldn't find that order." }) : null,
      );
    return () => {
      active = false;
    };
  }, [reference, status]);

  if (status === "anonymous") {
    return (
      <Section eyebrow="Order" heading="Sign in to view this order">
        <Link to="/" className="text-sm text-brand underline-offset-4 hover:underline">
          Back home
        </Link>
      </Section>
    );
  }

  if (state.kind === "loading") {
    return (
      <Section eyebrow="Order" heading="Loading your order…">
        <p className="text-sm text-ink-muted">One moment.</p>
      </Section>
    );
  }

  if (state.kind === "error") {
    return (
      <Section eyebrow="Order" heading="Order not found">
        <p className="text-sm text-ink-muted">{state.message}</p>
        <Link
          to="/account"
          className="mt-4 inline-flex text-sm text-brand underline-offset-4 hover:underline"
        >
          Your account
        </Link>
      </Section>
    );
  }

  const { order } = state;
  const paid = order.paymentStatus === "paid";

  return (
    <Section eyebrow="Track your order" heading={order.reference}>
      <div className="mb-6 flex flex-wrap items-center gap-2 rounded-sm border border-brand/30 bg-subtle/40 px-4 py-3 text-sm text-ink">
        <CheckCircle2 size={18} className="text-brand" aria-hidden />
        <span className="capitalize">Status: {order.orderStatus.replaceAll("_", " ")}</span>
        <span className="text-ink-muted">·</span>
        <span>Payment: {paid ? "Paid" : order.paymentStatus.replaceAll("_", " ")}</span>
      </div>

      <div className="grid gap-8 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <TrackingTimeline order={order} />

          <div className="overflow-x-auto rounded-md border border-line bg-surface">
            <table className="w-full min-w-[420px] text-left text-sm">
              <thead className="bg-canvas text-xs text-ink-muted uppercase">
                <tr>
                  <th className="px-4 py-2.5">Item</th>
                  <th className="px-4 py-2.5">Qty</th>
                  <th className="px-4 py-2.5">Total</th>
                </tr>
              </thead>
              <tbody>
                {order.items.map((item) => (
                  <tr key={item.id} className="border-t border-line">
                    <td className="px-4 py-3">
                      <span className="block font-medium text-ink">{item.productName}</span>
                      <span className="text-xs text-ink-muted">{item.variantName}</span>
                    </td>
                    <td className="px-4 py-3">{item.quantity}</td>
                    <td className="px-4 py-3">
                      {formatMoney(item.lineTotalMinor, order.currencyCode)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <aside className="h-fit rounded-md border border-line bg-surface p-5 shadow-card">
          <h2 className="font-display text-lg text-ink">Summary</h2>
          <dl className="mt-3 space-y-1.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-muted">Subtotal</dt>
              <dd>{formatMoney(order.subtotalMinor, order.currencyCode)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-muted">Delivery</dt>
              <dd>
                {order.deliveryMinor === 0
                  ? "Free"
                  : formatMoney(order.deliveryMinor, order.currencyCode)}
              </dd>
            </div>
            <div className="flex justify-between border-t border-line pt-1.5 font-medium">
              <dt>Total</dt>
              <dd>{formatMoney(order.totalMinor, order.currencyCode)}</dd>
            </div>
          </dl>
          <Link
            to="/account"
            className="mt-5 inline-flex text-sm text-brand underline-offset-4 hover:underline"
          >
            All your orders
          </Link>
        </aside>
      </div>
    </Section>
  );
}
