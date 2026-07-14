import { formatMoney } from "@truegrit/contracts";
import { CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import type { Route } from "./+types/order";
import { Section } from "../components/catalogue";
import { getMyOrder, type OrderDetail } from "../lib/commerce";
import { useCustomer } from "../lib/customer-auth";
import { seoMeta } from "../lib/seo";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Your order",
    description: "Order details.",
    canonicalPath: "/account",
    indexing: "noindex",
  });
}

type State =
  { kind: "loading" } | { kind: "error"; message: string } | { kind: "loaded"; order: OrderDetail };

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

  return (
    <Section eyebrow="Order" heading={order.reference}>
      <div className="mb-6 flex items-center gap-2 rounded-sm border border-brand/30 bg-subtle/40 px-4 py-3 text-sm text-ink">
        <CheckCircle2 size={18} className="text-brand" aria-hidden />
        <span>
          Order confirmed — {order.orderStatus.replaceAll("_", " ")}. Payment: cash on delivery (
          {order.paymentStatus}).
        </span>
      </div>

      <div className="grid gap-8 lg:grid-cols-[2fr_1fr]">
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
