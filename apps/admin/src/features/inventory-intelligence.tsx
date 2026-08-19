import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { DemandForecastPoint, InventoryIntelligenceItem } from "@truegrit/contracts";
import { RefreshCw, TrendingDown } from "lucide-react";
import { useMemo, useState } from "react";

import {
  Button,
  DataTableShell,
  EmptyState,
  Field,
  Input,
  LoadingRows,
  Modal,
  PageHeader,
  Td,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { T } from "../lib/i18n";
import { PermissionGate } from "../lib/permissions";

function KpiCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-md border border-line bg-surface p-4">
      <p className="text-xs font-medium tracking-[0.06em] text-ink-muted uppercase">{label}</p>
      <p className="mt-1.5 font-display text-2xl text-ink">{value}</p>
      <p className="mt-0.5 text-xs text-ink-muted">{hint}</p>
    </div>
  );
}

function ForecastChart({ points }: { points: DemandForecastPoint[] }) {
  if (!points.length) return null;
  const width = 720;
  const height = 220;
  const padding = 16;
  const max = Math.max(...points.map((point) => point.upperUnits), 1);
  const x = (index: number) =>
    padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
  const y = (units: number) => height - padding - (units / max) * (height - padding * 2);
  const upper = points.map((point, index) => `${x(index)},${y(point.upperUnits)}`).join(" ");
  const lower = [...points]
    .reverse()
    .map((point, reverseIndex) => {
      const index = points.length - reverseIndex - 1;
      return `${x(index)},${y(point.lowerUnits)}`;
    })
    .join(" ");
  const predicted = points
    .map((point, index) => `${x(index)},${y(point.predictedUnits)}`)
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-52 w-full"
      role="img"
      aria-label="Thirty-day unit forecast with confidence interval"
    >
      <polygon points={`${upper} ${lower}`} className="fill-subtle" />
      <polyline
        points={predicted}
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        className="text-brand"
      />
      {points.map((point, index) =>
        index % 5 === 0 ? (
          <circle key={point.forecastDate} cx={x(index)} cy={y(point.predictedUnits)} r="3">
            <title>
              {point.forecastDate}: {point.predictedUnits.toFixed(1)} <T>units (</T>
              {point.lowerUnits.toFixed(1)}–{point.upperUnits.toFixed(1)})
            </title>
          </circle>
        ) : null,
      )}
    </svg>
  );
}

function ForecastDetail({
  item,
  onClose,
}: {
  item: InventoryIntelligenceItem;
  onClose: () => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [leadTimeDays, setLeadTimeDays] = useState(item.leadTimeDays);
  const [safetyStockDays, setSafetyStockDays] = useState(item.safetyStockDays);
  const forecast = useQuery({
    queryKey: ["inventory-forecast", item.variantId],
    queryFn: () => api.inventoryForecast(item.variantId),
  });
  const settings = useMutation({
    mutationFn: () =>
      api.updateInventoryForecastSettings(item.variantId, { leadTimeDays, safetyStockDays }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["inventory-intelligence"] });
      toast.success("Lead time saved. It will apply to the next forecast run.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save lead time."),
  });
  return (
    <Modal title={`${item.productName} · ${item.variantName}`} onClose={onClose}>
      <div className="space-y-6">
        <div>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-ink">
                <T>30-day demand</T>
              </p>
              <p className="text-xs text-ink-muted">
                <T>Shaded area is the 95% residual interval; the line is expected daily units.</T>
              </p>
            </div>
            <span className="rounded-full bg-canvas px-2.5 py-1 text-xs text-ink-muted">
              {item.dataDays} <T>data days</T>
            </span>
          </div>
          {forecast.isLoading ? (
            <p className="mt-5 text-sm text-ink-muted">
              <T>Loading forecast...</T>
            </p>
          ) : (
            <ForecastChart points={forecast.data?.items ?? []} />
          )}
        </div>

        <PermissionGate permission="inventory.adjust">
          <form
            className="grid gap-4 border-t border-line pt-5 sm:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              settings.mutate();
            }}
          >
            <Field label="Restock lead time (days)" htmlFor="forecast-lead-time">
              <Input
                id="forecast-lead-time"
                type="number"
                min={1}
                max={90}
                value={leadTimeDays}
                onChange={(event) => setLeadTimeDays(Number(event.target.value))}
              />
            </Field>
            <Field label="Safety stock (days)" htmlFor="forecast-safety-stock">
              <Input
                id="forecast-safety-stock"
                type="number"
                min={0}
                max={30}
                value={safetyStockDays}
                onChange={(event) => setSafetyStockDays(Number(event.target.value))}
              />
            </Field>
            <div className="sm:col-span-2 flex justify-end">
              <Button type="submit" variant="primary" disabled={settings.isPending}>
                {settings.isPending ? <T>Saving...</T> : <T>Save planning settings</T>}
              </Button>
            </div>
          </form>
        </PermissionGate>
      </div>
    </Modal>
  );
}

export function InventoryIntelligencePage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [onlyReorder, setOnlyReorder] = useState(false);
  const [selected, setSelected] = useState<InventoryIntelligenceItem | null>(null);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["inventory-intelligence"],
    queryFn: api.inventoryIntelligence,
  });
  const recompute = useMutation({
    mutationFn: api.recomputeInventoryForecasts,
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["inventory-intelligence"] });
      toast.success(`Forecast refreshed for ${result.variants} SKUs.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not refresh forecasts."),
  });
  const items = useMemo(
    () => (data?.items ?? []).filter((item) => !onlyReorder || item.reorderRecommended),
    [data?.items, onlyReorder],
  );

  return (
    <div>
      <PageHeader
        title="Inventory Intelligence"
        description="SKU demand, days until stockout and reorder quantities from rolling sales and weekday seasonality."
        actions={
          <PermissionGate permission="inventory.adjust">
            <Button
              type="button"
              variant="secondary"
              disabled={recompute.isPending}
              onClick={() => recompute.mutate()}
            >
              <RefreshCw size={15} className={recompute.isPending ? "animate-spin" : ""} />
              {recompute.isPending ? <T>Forecasting...</T> : <T>Run forecast now</T>}
            </Button>
          </PermissionGate>
        }
      />

      {isError ? (
        <EmptyState
          title="Forecast unavailable"
          hint="Requires inventory.view and migration 0111."
        />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <KpiCard
              label="Reorder soon"
              value={String(data?.summary.reorderSoon ?? 0)}
              hint="Expected to run out inside lead time"
            />
            <KpiCard
              label="Forecasted SKUs"
              value={String(data?.summary.forecastedSkus ?? 0)}
              hint="Active, published variants"
            />
            <KpiCard
              label="Last refresh"
              value={
                data?.run
                  ? (formatDateTime(data.run.completedAt).split(",")[0] ?? "Not run")
                  : "Not run"
              }
              hint={data?.run?.modelVersion ?? "Run once to establish a baseline"}
            />
          </div>

          <div className="flex items-center justify-between gap-4">
            <label className="inline-flex min-h-9 cursor-pointer items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                checked={onlyReorder}
                onChange={(event) => setOnlyReorder(event.target.checked)}
              />
              <T>Show reorder recommendations only</T>
            </label>
            <p className="text-xs text-ink-muted">
              {data?.run ? `${data.run.horizonDays}-day horizon` : <T>{"No completed run"}</T>}
            </p>
          </div>

          {!isLoading && data?.run === null ? (
            <EmptyState
              title="No forecast yet"
              hint="Run the baseline once; it will then refresh every Monday."
            />
          ) : (
            <DataTableShell>
              <thead className="bg-canvas">
                <tr>
                  <Th>
                    <T>Product / SKU</T>
                  </Th>
                  <Th>
                    <T>Available</T>
                  </Th>
                  <Th>
                    <T>Daily demand</T>
                  </Th>
                  <Th>
                    <T>Days left</T>
                  </Th>
                  <Th>
                    <T>Lead time</T>
                  </Th>
                  <Th>
                    <T>Recommended order</T>
                  </Th>
                  <Th>
                    <T>Status</T>
                  </Th>
                </tr>
              </thead>
              {isLoading ? (
                <LoadingRows columns={7} />
              ) : (
                <tbody>
                  {items.map((item) => (
                    <tr
                      key={item.variantId}
                      className="cursor-pointer border-t border-line hover:bg-canvas/60"
                      onClick={() => setSelected(item)}
                    >
                      <Td>
                        <p className="font-medium text-ink">{item.productName}</p>
                        <p className="text-xs text-ink-muted">
                          {item.variantName} · {item.sku}
                        </p>
                      </Td>
                      <Td className="font-medium">{item.availableUnits}</Td>
                      <Td>
                        <span className="text-ink">{item.avgDaily7.toFixed(1)}</span>
                        <span className="text-xs text-ink-muted">
                          {" "}
                          <T>/ 7d</T>
                        </span>
                        <p className="text-xs text-ink-muted">
                          {item.avgDaily30.toFixed(1)} <T>/ 30d</T>
                        </p>
                      </Td>
                      <Td>
                        {item.daysUntilStockout === null ? "—" : item.daysUntilStockout.toFixed(1)}
                        {item.projectedStockoutDate ? (
                          <p className="text-xs text-ink-muted">{item.projectedStockoutDate}</p>
                        ) : null}
                      </Td>
                      <Td>
                        {item.leadTimeDays}
                        <T>d +</T> {item.safetyStockDays}d
                      </Td>
                      <Td className="font-medium">{item.recommendedOrderUnits || "—"}</Td>
                      <Td>
                        {item.reorderRecommended ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning">
                            <TrendingDown size={13} /> <T>Reorder soon</T>
                          </span>
                        ) : (
                          <span className="rounded-full bg-subtle px-2.5 py-1 text-xs font-medium text-brand">
                            <T>Stock healthy</T>
                          </span>
                        )}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              )}
            </DataTableShell>
          )}
        </div>
      )}
      {selected ? <ForecastDetail item={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}
