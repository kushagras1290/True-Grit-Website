/** Owner analytics dashboard (migration 0065): revenue, orders, top products
 * and order-status mix over a date range, computed live from orders/order_items
 * -- never a stored rollup. Distinct from Owner Reports (a curated,
 * parameterized query library with no charts): this is "how is the store
 * doing", glanced at rather than exported.
 *
 * The bar chart is hand-rolled SVG rather than a charting dependency -- this
 * admin bundle ships to a Cloudflare Worker, and a handful of <rect>s cover
 * everything a single revenue-trend needs. */

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { EmptyState, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { formatMoney } from "../lib/format";
import { T } from "../lib/i18n";

type RangePreset = 7 | 30 | 90;

function isoDaysAgo(days: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() - days);
  return date.toISOString().slice(0, 10);
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function KpiCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-md border border-line bg-surface p-4">
      <p className="text-xs font-medium tracking-[0.06em] text-ink-muted uppercase">{label}</p>
      <p className="mt-1.5 font-display text-2xl text-ink">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-ink-muted">{hint}</p> : null}
    </div>
  );
}

function RevenueChart({
  points,
}: {
  points: { date: string; revenueMinor: number; orderCount: number }[];
}) {
  if (points.length === 0) {
    return (
      <p className="text-sm text-ink-muted">
        <T>No orders in this range.</T>
      </p>
    );
  }

  const width = 720;
  const height = 200;
  const padding = 8;
  const max = Math.max(...points.map((point) => point.revenueMinor), 1);
  const barWidth = (width - padding * 2) / points.length;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-48 w-full"
      role="img"
      aria-label="Daily revenue for the selected range"
    >
      {points.map((point, index) => {
        const barHeight = Math.max((point.revenueMinor / max) * (height - padding * 2), 1);
        const x = padding + index * barWidth;
        const y = height - padding - barHeight;
        return (
          <g key={point.date}>
            <rect
              x={x + barWidth * 0.12}
              y={y}
              width={Math.max(barWidth * 0.76, 1)}
              height={barHeight}
              className="fill-brand"
            >
              <title>
                {point.date}: {formatMoney(point.revenueMinor, "INR")} across {point.orderCount}{" "}
                order{point.orderCount === 1 ? "" : "s"}
              </title>
            </rect>
          </g>
        );
      })}
    </svg>
  );
}

function StatusBreakdown({ rows }: { rows: { status: string; orderCount: number }[] }) {
  const total = rows.reduce((sum, row) => sum + row.orderCount, 0);
  if (total === 0)
    return (
      <p className="text-sm text-ink-muted">
        <T>No orders in this range.</T>
      </p>
    );
  return (
    <ul className="space-y-2">
      {rows.map((row) => {
        const percent = Math.round((row.orderCount / total) * 100);
        return (
          <li key={row.status}>
            <div className="flex items-center justify-between text-sm">
              <span className="text-ink capitalize">{row.status.replaceAll("_", " ")}</span>
              <span className="text-ink-muted">
                {row.orderCount} · {percent}%
              </span>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-canvas">
              <div
                className="h-1.5 rounded-full bg-brand"
                style={{ width: `${Math.max(percent, 2)}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function AnalyticsPage() {
  const [preset, setPreset] = useState<RangePreset>(30);
  const range = useMemo(() => ({ from: isoDaysAgo(preset - 1), to: todayIso() }), [preset]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin-analytics-overview", range.from, range.to],
    queryFn: () => api.analyticsOverview(range),
  });

  return (
    <div>
      <PageHeader
        title="Analytics"
        description="Revenue, orders and top products, computed live from real orders -- never a stored rollup that can drift from what checkout actually recorded."
        actions={
          <div className="flex gap-1.5">
            {([7, 30, 90] as const).map((days) => (
              <button
                key={days}
                type="button"
                onClick={() => setPreset(days)}
                className={`min-h-9 rounded-sm border px-3 text-xs font-medium ${
                  preset === days
                    ? "border-brand bg-subtle text-brand"
                    : "border-line-strong text-ink hover:bg-canvas"
                }`}
              >
                {days} days
              </button>
            ))}
          </div>
        }
      />

      {isLoading ? (
        <p className="text-sm text-ink-muted">
          <T>Loading analytics...</T>
        </p>
      ) : isError || !data ? (
        <EmptyState title="Analytics unavailable" hint="Requires the analytics.view permission." />
      ) : (
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard label="Revenue" value={formatMoney(data.revenueMinor, "INR")} />
            <KpiCard label="Orders" value={String(data.orderCount)} />
            <KpiCard
              label="Average order value"
              value={formatMoney(data.averageOrderValueMinor, "INR")}
            />
            <KpiCard label="New customers" value={String(data.newCustomers)} />
          </div>

          <div className="rounded-md border border-line bg-surface p-5">
            <h2 className="font-display text-lg text-ink">
              <T>Revenue by day</T>
            </h2>
            <div className="mt-4">
              <RevenueChart points={data.revenueByDay} />
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-md border border-line bg-surface p-5">
              <h2 className="font-display text-lg text-ink">
                <T>Top products</T>
              </h2>
              {data.topProducts.length === 0 ? (
                <p className="mt-2 text-sm text-ink-muted">
                  <T>No orders in this range.</T>
                </p>
              ) : (
                <ol className="mt-3 divide-y divide-line">
                  {data.topProducts.map((product, index) => (
                    <li
                      key={product.productId ?? product.productName}
                      className="flex items-center justify-between gap-3 py-2.5"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm text-ink">
                          <span className="text-ink-muted">{index + 1}.</span> {product.productName}
                        </p>
                        <p className="text-xs text-ink-muted">
                          {product.unitsSold} <T>units sold</T>
                        </p>
                      </div>
                      <span className="shrink-0 text-sm font-medium text-ink">
                        {formatMoney(product.revenueMinor, "INR")}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </div>

            <div className="rounded-md border border-line bg-surface p-5">
              <h2 className="font-display text-lg text-ink">
                <T>Order status mix</T>
              </h2>
              <div className="mt-3">
                <StatusBreakdown rows={data.statusBreakdown} />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
