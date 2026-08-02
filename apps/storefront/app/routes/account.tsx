import { formatMoney, type SubscriptionRow } from "@truegrit/contracts";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";

import type { Route } from "./+types/account";
import { Section } from "../components/catalogue";
import {
  cancelSubscription,
  listMyOrders,
  listMySubscriptions,
  pauseSubscription,
  resumeSubscription,
  type OrderSummary,
} from "../lib/commerce";
import { useCustomer } from "../lib/customer-auth";
import { seoMeta } from "../lib/seo";

const FREQUENCY_LABELS: Record<string, string> = {
  weekly: "Every week",
  biweekly: "Every 2 weeks",
  monthly: "Every month",
};

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Your account",
    description: "Manage your True Grit account.",
    canonicalPath: "/account",
    indexing: "noindex",
  });
}

function OrderHistory() {
  const [orders, setOrders] = useState<OrderSummary[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    listMyOrders()
      .then((items) => active && setOrders(items))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, []);

  if (failed) {
    return <p className="text-sm text-ink-muted">Order history is unavailable right now.</p>;
  }
  if (orders === null) {
    return <p className="text-sm text-ink-muted">Loading your orders…</p>;
  }
  if (orders.length === 0) {
    return (
      <p className="text-sm text-ink-muted">
        No orders yet.{" "}
        <Link to="/shop" className="text-brand underline-offset-4 hover:underline">
          Start shopping
        </Link>
        .
      </p>
    );
  }

  return (
    <ul className="divide-y divide-line rounded-md border border-line bg-surface">
      {orders.map((order) => (
        <li key={order.reference} className="flex items-center justify-between gap-3 px-5 py-4">
          <div className="min-w-0">
            <Link
              to={`/account/orders/${order.reference}`}
              className="font-medium text-brand hover:underline"
            >
              {order.reference}
            </Link>
            <p className="mt-0.5 text-xs text-ink-muted">
              {new Date(order.placedAt).toLocaleDateString()} · {order.itemCount} item
              {order.itemCount === 1 ? "" : "s"} ·{" "}
              <span className="capitalize">{order.orderStatus.replaceAll("_", " ")}</span>
            </p>
            <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-ink-muted">
              <span className="inline-flex items-center rounded-sm bg-canvas px-1.5 py-0.5 capitalize">
                Payment: {order.paymentStatus.replaceAll("_", " ")}
              </span>
              <span className="inline-flex items-center rounded-sm bg-canvas px-1.5 py-0.5 capitalize">
                Fulfilment: {order.fulfilmentStatus.replaceAll("_", " ")}
              </span>
            </div>
          </div>
          <span className="whitespace-nowrap text-sm font-medium text-ink">
            {formatMoney(order.totalMinor, order.currencyCode)}
          </span>
        </li>
      ))}
    </ul>
  );
}

function MySubscriptions() {
  const [subscriptions, setSubscriptions] = useState<SubscriptionRow[] | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listMySubscriptions()
      .then((items) => active && setSubscriptions(items))
      .catch(() => active && setSubscriptions([]));
    return () => {
      active = false;
    };
  }, []);

  async function act(id: string, action: "pause" | "resume" | "cancel") {
    setBusyId(id);
    try {
      const updated = await (action === "pause"
        ? pauseSubscription(id)
        : action === "resume"
          ? resumeSubscription(id)
          : cancelSubscription(id));
      setSubscriptions((current) =>
        (current ?? []).map((entry) => (entry.id === id ? updated : entry)),
      );
    } catch {
      // The list still reflects the last known state; a failed action simply
      // leaves it unchanged rather than showing a stale optimistic update.
    } finally {
      setBusyId(null);
    }
  }

  if (subscriptions === null) {
    return <p className="text-sm text-ink-muted">Loading your subscriptions…</p>;
  }
  if (subscriptions.length === 0) {
    return (
      <p className="text-sm text-ink-muted">
        No subscriptions yet. Look for "Subscribe & Save" on a product page to set up recurring
        delivery.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-line rounded-md border border-line bg-surface">
      {subscriptions.map((entry) => (
        <li key={entry.id} className="flex items-center justify-between gap-3 px-5 py-4">
          <div className="min-w-0">
            <p className="font-medium text-ink">
              {entry.quantity} × {entry.productName} — {entry.variantName}
            </p>
            <p className="mt-0.5 text-xs text-ink-muted">
              {FREQUENCY_LABELS[entry.frequency] ?? entry.frequency} ·{" "}
              <span className="capitalize">{entry.status}</span>
              {entry.status !== "cancelled"
                ? ` · next delivery ${new Date(entry.nextOrderDate).toLocaleDateString()}`
                : ""}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            {entry.status === "active" ? (
              <button
                type="button"
                disabled={busyId === entry.id}
                onClick={() => act(entry.id, "pause")}
                className="min-h-9 rounded-sm border border-line-strong px-3 text-xs font-medium text-ink hover:bg-canvas disabled:opacity-50"
              >
                Pause
              </button>
            ) : null}
            {entry.status === "paused" ? (
              <button
                type="button"
                disabled={busyId === entry.id}
                onClick={() => act(entry.id, "resume")}
                className="min-h-9 rounded-sm border border-line-strong px-3 text-xs font-medium text-ink hover:bg-canvas disabled:opacity-50"
              >
                Resume
              </button>
            ) : null}
            {entry.status !== "cancelled" ? (
              <button
                type="button"
                disabled={busyId === entry.id}
                onClick={() => act(entry.id, "cancel")}
                className="min-h-9 rounded-sm border border-danger/40 px-3 text-xs font-medium text-danger hover:bg-danger/5 disabled:opacity-50"
              >
                Cancel
              </button>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function AccountPage(_props: Route.ComponentProps) {
  const { customer, status, logout } = useCustomer();
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);

  if (status === "loading") {
    return (
      <Section eyebrow="Account" heading="Loading your account">
        <p className="text-sm text-ink-muted">One moment…</p>
      </Section>
    );
  }

  if (status === "anonymous" || customer === null) {
    return (
      <Section eyebrow="Account" heading="You're signed out">
        <p className="max-w-md text-sm text-ink-muted">
          Open the account menu in the header to sign in with Google or your email and password.
          Your basket is saved on this device in the meantime.
        </p>
        <Link
          to="/shop"
          className="mt-5 inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90"
        >
          Continue shopping
        </Link>
      </Section>
    );
  }

  async function handleSignOut() {
    setSigningOut(true);
    await logout();
    setSigningOut(false);
    void navigate("/");
  }

  return (
    <Section eyebrow="Account" heading={`Hello, ${customer.displayName}`}>
      <div className="grid gap-8 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <dl className="divide-y divide-line rounded-md border border-line bg-surface">
            <div className="flex items-center justify-between px-5 py-4">
              <dt className="text-sm text-ink-muted">Name</dt>
              <dd className="text-sm font-medium text-ink">{customer.displayName}</dd>
            </div>
            {/* Phone-only accounts have no address at all, so render the row
                only when there is something real to put in it. */}
            {customer.email ? (
              <div className="flex items-center justify-between px-5 py-4">
                <dt className="text-sm text-ink-muted">Email</dt>
                <dd className="text-sm font-medium text-ink">{customer.email}</dd>
              </div>
            ) : null}
            <div className="flex items-center justify-between px-5 py-4">
              <dt className="text-sm text-ink-muted">Mobile</dt>
              <dd className="text-sm font-medium text-ink">
                {customer.phone ?? <span className="text-ink-muted">Not added</span>}
              </dd>
            </div>
          </dl>

          <div>
            <h2 className="mb-2 font-display text-lg text-ink">Order history</h2>
            <OrderHistory />
          </div>

          <div>
            <h2 className="mb-2 font-display text-lg text-ink">Subscriptions</h2>
            <MySubscriptions />
          </div>
        </div>

        <aside className="h-fit space-y-4 rounded-md border border-line bg-surface p-5 shadow-card">
          <Link
            to="/cart"
            className="inline-flex min-h-11 w-full items-center justify-center rounded-sm border border-line px-4 text-sm font-medium text-ink hover:bg-canvas"
          >
            View basket
          </Link>
          <Link
            to="/account/submissions"
            className="inline-flex min-h-11 w-full items-center justify-center rounded-sm border border-line px-4 text-sm font-medium text-ink hover:bg-canvas"
          >
            Your submissions
          </Link>
          <Link
            to="/community"
            className="inline-flex min-h-11 w-full items-center justify-center rounded-sm border border-line px-4 text-sm font-medium text-ink hover:bg-canvas"
          >
            Community
          </Link>
          <button
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
            className="min-h-11 w-full rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-95 disabled:opacity-60"
          >
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </aside>
      </div>
    </Section>
  );
}
