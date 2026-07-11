/** Dashboard: only actionable numbers, each linking to its operational view. */

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { EmptyState, PageHeader, StatusPill } from "../components/ui";
import { api } from "../lib/api";
import { formatDateTime, formatMoney } from "../lib/format";

function StatCard({
  label,
  value,
  to,
  tone,
}: {
  label: string;
  value: string;
  to: string;
  tone?: "warn";
}) {
  return (
    <Link
      to={to}
      className="block rounded-md border border-line bg-surface px-4 py-4 shadow-card transition-opacity hover:opacity-85"
    >
      <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">{label}</p>
      <p className={`mt-1.5 font-display text-2xl ${tone === "warn" ? "text-accent" : "text-ink"}`}>
        {value}
      </p>
    </Link>
  );
}

export function DashboardPage() {
  const orders = useQuery({ queryKey: ["orders"], queryFn: api.orders });
  const inventory = useQuery({ queryKey: ["inventory"], queryFn: api.inventory });
  const audit = useQuery({ queryKey: ["audit"], queryFn: api.audit });

  const paidOrders = (orders.data ?? []).filter((order) => order.paymentStatus === "paid");
  const revenueMinor = paidOrders.reduce((sum, order) => sum + order.totalMinor, 0);
  const pendingFulfilment = (orders.data ?? []).filter(
    (order) => order.orderStatus === "confirmed" || order.orderStatus === "processing",
  ).length;
  const lowStock = (inventory.data ?? []).filter(
    (row) => row.onHand - row.reserved <= row.reorderThreshold,
  );

  return (
    <div>
      <PageHeader
        title="Overview"
        description="Today across the marketplace. Every number links to the queue that clears it."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Revenue (paid)" value={formatMoney(revenueMinor)} to="/orders" />
        <StatCard label="Orders" value={String(orders.data?.length ?? "—")} to="/orders" />
        <StatCard
          label="Pending fulfilment"
          value={String(pendingFulfilment)}
          to="/orders"
          tone={pendingFulfilment > 0 ? "warn" : undefined}
        />
        <StatCard
          label="Low stock variants"
          value={String(lowStock.length)}
          to="/inventory"
          tone={lowStock.length > 0 ? "warn" : undefined}
        />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="attention-heading">
          <h2 id="attention-heading" className="mb-3 font-display text-lg text-ink">
            Needs attention
          </h2>
          {lowStock.length === 0 ? (
            <EmptyState title="Nothing urgent" hint="Low-stock and exception queues are clear." />
          ) : (
            <ul className="divide-y divide-line rounded-md border border-line bg-surface shadow-card">
              {lowStock.map((row) => (
                <li
                  key={row.variantId}
                  className="flex items-center justify-between gap-3 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-ink">{row.productName}</p>
                    <p className="text-xs text-ink-muted">
                      {row.variantName} · {row.sku}
                    </p>
                  </div>
                  <div className="text-right">
                    <StatusPill
                      status={row.onHand - row.reserved <= 0 ? "out_of_stock" : "low_stock"}
                    />
                    <p className="mt-1 text-xs text-ink-muted">
                      {row.onHand - row.reserved} available · reorder at {row.reorderThreshold}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="activity-heading">
          <h2 id="activity-heading" className="mb-3 font-display text-lg text-ink">
            Recent administrative activity
          </h2>
          <ul className="divide-y divide-line rounded-md border border-line bg-surface shadow-card">
            {(audit.data ?? []).slice(0, 6).map((entry) => (
              <li key={entry.id} className="px-4 py-3">
                <p className="text-sm text-ink">
                  <span className="font-medium">{entry.actorName}</span>{" "}
                  <span className="text-ink-muted">{entry.action.replaceAll(".", " · ")}</span>
                </p>
                <p className="text-xs text-ink-muted">{formatDateTime(entry.createdAt)}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
