/**
 * A printable/downloadable e-receipt for one order -- the browser's own
 * "Print" / "Save as PDF" does the export, so there is no server-side PDF
 * renderer to fit inside the Workers Free plan's tight CPU budget (see the
 * comment in apps/api/wrangler.jsonc). `print:hidden` on the site header and
 * footer (components/chrome.tsx) already keeps navigation chrome out of the
 * printed page; this route's own layout is deliberately plain -- a document,
 * not a marketing section.
 */

import { formatMoney } from "@truegrit/contracts";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import type { Route } from "./+types/receipt";
import { getMyOrder, type OrderDetail } from "../lib/commerce";
import { useCustomer } from "../lib/customer-auth";
import { seoMeta } from "../lib/seo";
import { LocalizedText } from "../lib/i18n/localized-text";

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Order receipt",
    description: "Printable receipt for a True Grit order.",
    canonicalPath: "/account",
    indexing: "noindex",
  });
}

type State =
  { kind: "loading" } | { kind: "loaded"; order: OrderDetail } | { kind: "error"; message: string };

export default function ReceiptPage(_props: Route.ComponentProps) {
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
      <div className="mx-auto max-w-2xl px-4 py-14 text-sm text-ink-muted">
        <LocalizedText>Sign in to view this receipt.</LocalizedText>
      </div>
    );
  }

  if (state.kind === "loading") {
    return (
      <div className="mx-auto max-w-2xl px-4 py-14 text-sm text-ink-muted">
        <LocalizedText>One moment…</LocalizedText>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="mx-auto max-w-2xl px-4 py-14">
        <p className="text-sm text-ink-muted">{state.message}</p>
        <Link to="/account" className="mt-4 inline-flex text-sm text-brand hover:underline">
          <LocalizedText>Your account</LocalizedText>
        </Link>
      </div>
    );
  }

  const { order } = state;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6 print:max-w-none print:px-0 print:py-0">
      <div className="mb-6 flex justify-end gap-3 print:hidden">
        <Link
          to={`/account/orders/${reference}`}
          className="inline-flex min-h-10 items-center rounded-sm border border-line-strong px-4 text-sm font-medium text-ink hover:bg-canvas"
        >
          <LocalizedText>Back to order</LocalizedText>
        </Link>
        <button
          type="button"
          onClick={() => window.print()}
          className="inline-flex min-h-10 items-center rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-90"
        >
          <LocalizedText>Print / Save as PDF</LocalizedText>
        </button>
      </div>

      <div className="rounded-md border border-line bg-surface p-8 print:rounded-none print:border-0 print:p-0">
        <div className="flex items-start justify-between gap-4 border-b border-line pb-6">
          <div className="flex items-center gap-3">
            <img
              src="/brand/true-grit-mark.webp"
              alt=""
              width={44}
              height={44}
              className="h-11 w-11 rounded-full object-cover"
            />
            <div>
              <p className="font-display text-xl font-semibold text-ink">TRUE GRIT</p>
              <p className="text-xs text-ink-muted">
                <LocalizedText>Order receipt</LocalizedText>
              </p>
            </div>
          </div>
          <div className="text-right text-sm">
            <p className="font-medium text-ink">{order.reference}</p>
            <p className="text-ink-muted">{new Date(order.placedAt).toLocaleDateString()}</p>
          </div>
        </div>

        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold tracking-[0.08em] text-ink-muted uppercase">
              <LocalizedText>Delivered to</LocalizedText>
            </p>
            {order.deliveryAddress ? (
              <address className="mt-1.5 text-sm not-italic text-ink">
                <p>{order.deliveryAddress.recipientName}</p>
                <p>{order.deliveryAddress.line1}</p>
                {order.deliveryAddress.line2 ? <p>{order.deliveryAddress.line2}</p> : null}
                <p>
                  {order.deliveryAddress.city}, {order.deliveryAddress.state}{" "}
                  {order.deliveryAddress.postalCode}
                </p>
                {order.deliveryAddress.phoneE164 ? <p>{order.deliveryAddress.phoneE164}</p> : null}
              </address>
            ) : (
              <p className="mt-1.5 text-sm text-ink-muted">
                <LocalizedText>Not available.</LocalizedText>
              </p>
            )}
          </div>
          <div className="sm:text-right">
            <p className="text-xs font-semibold tracking-[0.08em] text-ink-muted uppercase">
              <LocalizedText>Status</LocalizedText>
            </p>
            <p className="mt-1.5 text-sm text-ink capitalize">
              {order.orderStatus.replaceAll("_", " ")}
            </p>
            <p className="text-sm text-ink-muted capitalize">
              <LocalizedText>Payment:</LocalizedText> {order.paymentStatus.replaceAll("_", " ")}
            </p>
          </div>
        </div>

        <table className="mt-8 w-full text-left text-sm">
          <thead>
            <tr className="border-b border-line text-xs text-ink-muted uppercase">
              <th className="py-2 font-medium">
                <LocalizedText>Item</LocalizedText>
              </th>
              <th className="py-2 text-right font-medium">
                <LocalizedText>Qty</LocalizedText>
              </th>
              <th className="py-2 text-right font-medium">
                <LocalizedText>Unit</LocalizedText>
              </th>
              <th className="py-2 text-right font-medium">
                <LocalizedText>Total</LocalizedText>
              </th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((item) => (
              <tr key={item.id} className="border-b border-line/60">
                <td className="py-2.5 text-ink">
                  {item.productName} — {item.variantName}
                  <span className="block text-xs text-ink-muted">{item.sku}</span>
                </td>
                <td className="py-2.5 text-right text-ink">{item.quantity}</td>
                <td className="py-2.5 text-right text-ink">
                  {formatMoney(item.unitMinor, order.currencyCode)}
                </td>
                <td className="py-2.5 text-right text-ink">
                  {formatMoney(item.lineTotalMinor, order.currencyCode)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-4 flex justify-end">
          <dl className="w-full max-w-xs space-y-1.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-muted">
                <LocalizedText>Subtotal</LocalizedText>
              </dt>
              <dd className="text-ink">{formatMoney(order.subtotalMinor, order.currencyCode)}</dd>
            </div>
            {order.discountMinor > 0 ? (
              <div className="flex justify-between">
                <dt className="text-ink-muted">
                  <LocalizedText>Discount</LocalizedText>
                </dt>
                <dd className="text-success">
                  −{formatMoney(order.discountMinor, order.currencyCode)}
                </dd>
              </div>
            ) : null}
            <div className="flex justify-between">
              <dt className="text-ink-muted">
                <LocalizedText>Delivery</LocalizedText>
              </dt>
              <dd className="text-ink">
                {order.deliveryMinor > 0
                  ? formatMoney(order.deliveryMinor, order.currencyCode)
                  : "Free"}
              </dd>
            </div>
            {order.taxMinor > 0 ? (
              <div className="flex justify-between">
                <dt className="text-ink-muted">
                  <LocalizedText>Tax</LocalizedText>
                </dt>
                <dd className="text-ink">{formatMoney(order.taxMinor, order.currencyCode)}</dd>
              </div>
            ) : null}
            <div className="flex justify-between border-t border-line pt-1.5 text-base font-semibold">
              <dt className="text-ink">
                <LocalizedText>Total</LocalizedText>
              </dt>
              <dd className="text-ink">{formatMoney(order.totalMinor, order.currencyCode)}</dd>
            </div>
          </dl>
        </div>

        <p className="mt-8 border-t border-line pt-4 text-center text-xs text-ink-muted">
          <LocalizedText>Thank you for shopping with True Grit.</LocalizedText>
        </p>
      </div>
    </div>
  );
}
