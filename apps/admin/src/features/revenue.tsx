/**
 * Revenue console: what each farm has earned, the platform's cut, and paying
 * farms out.
 *
 * Two views:
 *   `/revenue`            — one row per farm, editable commission, outstanding
 *                           balance, and the payment action.
 *   `/revenue/:farmId`    — that farm's individual order lines and its payout
 *                           history, so any figure can be traced to its orders.
 *
 * Reading revenue (`revenue.view`) and moving money (`revenue.manage`) are
 * separate permissions. Hiding a control here is a courtesy — the API enforces
 * both independently.
 *
 * On wording: the payment action says "Record payment", not "Send". Recording
 * settles the lines in the ledger so they can never be paid twice; it does not
 * transfer money, because no disbursement rail is configured. Labelling it
 * "Send" would tell an operator money left the account when it did not.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  Button,
  DataTableShell,
  EmptyState,
  Field,
  Input,
  LoadingRows,
  Modal,
  PageHeader,
  StatusPill,
  Td,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import {
  ApiError,
  api,
  type FarmRevenueDetail,
  type FarmRevenueRow,
  type FarmPayout,
} from "../lib/api";
import { formatDate, formatDateTime, formatMoney } from "../lib/format";
import { usePermissions } from "../lib/permissions";
import { T } from "../lib/i18n";

const REVENUE_KEY = ["admin-revenue"];

/** Percentages arrive from the API as numbers (15, 12.5). Trailing-zero-free
 *  display keeps the table readable without hiding a real 12.5%. */
function formatPercent(percent: number): string {
  return `${Number.isInteger(percent) ? percent : percent.toFixed(2)}%`;
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

// --------------------------------------------------------------------------
// Commission editor
// --------------------------------------------------------------------------

/** Inline percentage editor used for both the house default and a single
 *  farm's override. Empty input means "clear the override" wherever clearing
 *  is allowed (`allowClear`), which is how a farm returns to the default —
 *  deliberately different from typing 0, which charges the farm nothing. */
function CommissionEditor({
  value,
  source,
  allowClear,
  disabled,
  onSave,
  isPending,
}: {
  value: number;
  source?: "farm" | "default";
  allowClear: boolean;
  disabled: boolean;
  onSave: (percent: number | null) => void;
  isPending: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(value));
  const [error, setError] = useState<string>();

  function open() {
    setDraft(source === "default" && allowClear ? "" : String(value));
    setError(undefined);
    setEditing(true);
  }

  function commit() {
    const trimmed = draft.trim();
    if (trimmed === "") {
      if (!allowClear) {
        setError("Enter a percentage.");
        return;
      }
      onSave(null);
      setEditing(false);
      return;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed) || parsed < 0 || parsed > 100) {
      setError("Enter 0–100.");
      return;
    }
    if (Math.abs(parsed * 100 - Math.round(parsed * 100)) > 1e-6) {
      setError("Two decimal places max.");
      return;
    }
    onSave(parsed);
    setEditing(false);
  }

  if (!editing) {
    return (
      <div className="flex items-center gap-2">
        <span className="font-medium tabular-nums">{formatPercent(value)}</span>
        {source === "default" ? (
          <span className="text-xs text-ink-muted" title="Following the default rate">
            default
          </span>
        ) : null}
        {!disabled ? (
          <button
            type="button"
            onClick={open}
            className="text-xs font-medium text-brand underline-offset-2 hover:underline"
          >
            <T>Edit</T>
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5">
        <Input
          aria-label="Commission percentage"
          className="w-24"
          value={draft}
          autoFocus
          inputMode="decimal"
          placeholder={allowClear ? "default" : "0"}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") commit();
            if (event.key === "Escape") setEditing(false);
          }}
        />
        <Button variant="primary" onClick={commit} disabled={isPending}>
          {isPending ? "…" : <T>{"Save"}</T>}
        </Button>
        <Button variant="secondary" onClick={() => setEditing(false)} disabled={isPending}>
          <T>Cancel</T>
        </Button>
      </div>
      {error ? <p className="text-xs font-medium text-danger">{error}</p> : null}
      {allowClear ? (
        <p className="text-xs text-ink-muted">
          <T>Leave blank to use the default.</T>
        </p>
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------
// Issue-payment dialog
// --------------------------------------------------------------------------

/** Confirms a payout and captures the out-of-band transfer reference.
 *
 * The dialog shows the full arithmetic — gross, refunds, the cut, the payable
 * amount — because the operator is approving a specific number, and the
 * request carries that number back (`expectedPayoutMinor`). If the balance
 * moved since the page loaded, the API refuses rather than paying a different
 * amount than the one on screen. */
function IssuePaymentDialog({ farm, onClose }: { farm: FarmRevenueRow; onClose: () => void }) {
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const toast = useToast();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () =>
      api.issueFarmPayout(farm.farmId, {
        reference,
        note,
        expectedPayoutMinor: farm.outstandingPayoutMinor,
      }),
    onSuccess: (result) => {
      toast.success(
        `Recorded ${formatMoney(result.payoutMinor, farm.currencyCode)} payable to ${farm.farmName}.`,
      );
      void queryClient.invalidateQueries({ queryKey: REVENUE_KEY });
      void queryClient.invalidateQueries({ queryKey: ["admin-farm-revenue", farm.farmId] });
      onClose();
    },
    onError: (error) => toast.error(errorMessage(error, "Could not record the payment.")),
  });

  return (
    <Modal title={`Record payment — ${farm.farmName}`} onClose={onClose}>
      <div className="space-y-4">
        <dl className="rounded-md border border-line bg-canvas p-3 text-sm">
          <Row
            label="Gross revenue"
            value={formatMoney(farm.outstandingGrossMinor, farm.currencyCode)}
          />
          <Row
            label="Less refunds"
            value={`− ${formatMoney(farm.outstandingRefundedMinor, farm.currencyCode)}`}
          />
          <Row
            label={`Less platform cut (${formatPercent(farm.commissionPercent)})`}
            value={`− ${formatMoney(farm.outstandingCommissionMinor, farm.currencyCode)}`}
          />
          <div className="mt-2 flex justify-between border-t border-line pt-2 font-semibold text-ink">
            <dt>
              <T>Payable to farm</T>
            </dt>
            <dd className="tabular-nums">
              {formatMoney(farm.outstandingPayoutMinor, farm.currencyCode)}
            </dd>
          </div>
        </dl>

        <p className="text-xs leading-5 text-ink-muted">
          <T>This records the payout against</T> {farm.outstandingItemCount} <T>order line</T>
          {farm.outstandingItemCount === 1 ? "" : "s"}{" "}
          <T>and marks them settled, so they can never be paid twice. It does</T>{" "}
          <strong>not</strong> <T>transfer money — make the transfer to</T>{" "}
          {farm.ownerName || farm.farmerName || <T>{"the farm owner"}</T>}{" "}
          <T>and file the reference below.</T>
        </p>

        <Field label="Transfer reference (UPI / bank / cheque)" htmlFor="payout-reference">
          <Input
            id="payout-reference"
            value={reference}
            maxLength={120}
            placeholder="e.g. UTR 123456789012"
            onChange={(event) => setReference(event.target.value)}
          />
        </Field>
        <Field label="Note (optional)" htmlFor="payout-note">
          <Input
            id="payout-note"
            value={note}
            maxLength={500}
            onChange={(event) => setNote(event.target.value)}
          />
        </Field>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            <T>Cancel</T>
          </Button>
          <Button
            variant="primary"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || farm.outstandingPayoutMinor <= 0}
          >
            {mutation.isPending ? <T>{"Recording…"}</T> : <T>{"Record payment"}</T>}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-0.5 text-ink-muted">
      <dt>{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  );
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-md border border-line bg-surface p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-ink">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-ink-muted">{hint}</p> : null}
    </div>
  );
}

// --------------------------------------------------------------------------
// Revenue list
// --------------------------------------------------------------------------

export function RevenuePage() {
  const permissions = usePermissions();
  const canManage = permissions.has("revenue.manage");
  const toast = useToast();
  const queryClient = useQueryClient();
  const [payingFarm, setPayingFarm] = useState<FarmRevenueRow | null>(null);

  const { data, isLoading, isError } = useQuery({ queryKey: REVENUE_KEY, queryFn: api.revenue });

  const defaultRate = useMutation({
    mutationFn: (percent: number) => api.setDefaultCommission(percent),
    onSuccess: () => {
      toast.success("Default commission updated.");
      void queryClient.invalidateQueries({ queryKey: REVENUE_KEY });
    },
    onError: (error) => toast.error(errorMessage(error, "Could not update the default rate.")),
  });

  const farmRate = useMutation({
    mutationFn: ({ farmId, percent }: { farmId: string; percent: number | null }) =>
      api.setFarmCommission(farmId, percent),
    onSuccess: () => {
      toast.success("Commission updated.");
      void queryClient.invalidateQueries({ queryKey: REVENUE_KEY });
    },
    onError: (error) => toast.error(errorMessage(error, "Could not update the commission.")),
  });

  if (isError) {
    return (
      <div>
        <PageHeader title="Revenue" />
        <EmptyState
          title="Revenue unavailable"
          hint="This page requires the revenue.view permission."
        />
      </div>
    );
  }

  const farms = data?.farms ?? [];
  const totals = data?.totals;
  const currency = farms[0]?.currencyCode ?? "INR";

  return (
    <div>
      <PageHeader
        title="Revenue"
        description="What each farm has earned, the platform's cut, and payments to farm owners."
      />

      {totals ? (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Net revenue"
            value={formatMoney(totals.netRevenueMinor, currency)}
            hint="After refunds, all farms"
          />
          <StatCard label="Platform cut" value={formatMoney(totals.commissionMinor, currency)} />
          <StatCard label="Paid out" value={formatMoney(totals.paidOutMinor, currency)} />
          <StatCard
            label="Outstanding"
            value={formatMoney(totals.outstandingPayoutMinor, currency)}
            hint="Payable to farms now"
          />
        </div>
      ) : null}

      {data ? (
        <div className="mb-6 flex flex-wrap items-center gap-3 rounded-md border border-line bg-surface p-4">
          <div className="min-w-0">
            <p className="text-sm font-medium text-ink">
              <T>Default commission</T>
            </p>
            <p className="text-xs text-ink-muted">
              <T>Applied to every farm without its own rate.</T>
            </p>
          </div>
          <div className="ml-auto">
            <CommissionEditor
              value={data.defaultCommissionPercent}
              allowClear={false}
              disabled={!canManage}
              isPending={defaultRate.isPending}
              onSave={(percent) => {
                if (percent !== null) defaultRate.mutate(percent);
              }}
            />
          </div>
        </div>
      ) : null}

      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>
              <T>Farm</T>
            </Th>
            <Th>
              <T>Net revenue</T>
            </Th>
            <Th>
              <T>Cut</T>
            </Th>
            <Th>
              <T>Platform earns</T>
            </Th>
            <Th>
              <T>Paid out</T>
            </Th>
            <Th>
              <T>Outstanding</T>
            </Th>
            <Th className="text-right">
              <T>Actions</T>
            </Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={7} />
        ) : farms.length === 0 ? (
          <tbody>
            <tr>
              <Td colSpan={7}>
                <EmptyState
                  title="No farms yet"
                  hint="Farms appear here once they exist and have sold something."
                />
              </Td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {farms.map((farm) => (
              <tr key={farm.farmId} className="border-t border-line align-top">
                <Td>
                  <span className="block font-medium text-ink">{farm.farmName}</span>
                  <span className="block text-xs text-ink-muted">
                    {farm.ownerName || farm.farmerName || <T>{"No owner linked"}</T>}
                    {farm.region ? ` · ${farm.region}` : ""}
                  </span>
                </Td>
                <Td className="tabular-nums">
                  {formatMoney(farm.netRevenueMinor, farm.currencyCode)}
                  {farm.refundedMinor > 0 ? (
                    <span className="block text-xs text-ink-muted">
                      after {formatMoney(farm.refundedMinor, farm.currencyCode)} refunded
                    </span>
                  ) : null}
                </Td>
                <Td>
                  <CommissionEditor
                    value={farm.commissionPercent}
                    source={farm.commissionSource}
                    allowClear
                    disabled={!canManage}
                    isPending={farmRate.isPending && farmRate.variables?.farmId === farm.farmId}
                    onSave={(percent) => farmRate.mutate({ farmId: farm.farmId, percent })}
                  />
                </Td>
                <Td className="tabular-nums">
                  {formatMoney(farm.commissionMinor, farm.currencyCode)}
                </Td>
                <Td className="tabular-nums">
                  {formatMoney(farm.paidOutMinor, farm.currencyCode)}
                  <span className="block text-xs text-ink-muted">
                    {farm.payoutCount} payment{farm.payoutCount === 1 ? "" : "s"}
                  </span>
                </Td>
                <Td className="tabular-nums font-medium">
                  {formatMoney(farm.outstandingPayoutMinor, farm.currencyCode)}
                  {farm.outstandingItemCount > 0 ? (
                    <span className="block text-xs font-normal text-ink-muted">
                      {farm.outstandingItemCount} line
                      {farm.outstandingItemCount === 1 ? "" : "s"}
                    </span>
                  ) : null}
                </Td>
                <Td className="text-right">
                  <div className="flex flex-wrap justify-end gap-2">
                    <Link
                      to={`/revenue/${farm.farmId}`}
                      className="inline-flex items-center rounded-sm border border-line px-2.5 py-1.5 text-xs font-medium text-ink hover:bg-subtle/50"
                    >
                      <T>Detailed revenue</T>
                    </Link>
                    {canManage ? (
                      <Button
                        variant="primary"
                        disabled={farm.outstandingPayoutMinor <= 0}
                        title={
                          farm.outstandingPayoutMinor <= 0
                            ? "Nothing outstanding to pay"
                            : undefined
                        }
                        onClick={() => setPayingFarm(farm)}
                      >
                        <T>Issue payment</T>
                      </Button>
                    ) : null}
                  </div>
                </Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>

      {payingFarm ? (
        <IssuePaymentDialog farm={payingFarm} onClose={() => setPayingFarm(null)} />
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------
// Per-farm detail
// --------------------------------------------------------------------------

export function FarmRevenueDetailPage() {
  const { farmId = "" } = useParams();
  const permissions = usePermissions();
  const canManage = permissions.has("revenue.manage");
  const [paying, setPaying] = useState(false);

  const { data, isLoading, isError } = useQuery<FarmRevenueDetail>({
    queryKey: ["admin-farm-revenue", farmId],
    queryFn: () => api.farmRevenue(farmId),
    enabled: farmId !== "",
  });

  if (isError) {
    return (
      <div>
        <PageHeader title="Farm revenue" />
        <EmptyState title="Farm not found" hint="It may have been removed." />
      </div>
    );
  }
  if (isLoading || !data) {
    return (
      <div>
        <PageHeader title="Farm revenue" />
        <p className="text-sm text-ink-muted">
          <T>Loading revenue…</T>
        </p>
      </div>
    );
  }

  const { summary, lines, payouts } = data;
  const unsettled = lines.filter((line) => !line.settled);

  return (
    <div>
      <PageHeader
        title={`${summary.farmName} — revenue`}
        description={`${summary.orderCount} order${summary.orderCount === 1 ? "" : "s"} · commission ${formatPercent(summary.commissionPercent)} (${summary.commissionSource === "farm" ? "farm rate" : "default rate"})`}
      />

      <div className="mb-4">
        <Link to="/revenue" className="text-sm text-brand underline-offset-2 hover:underline">
          <T>← All farms</T>
        </Link>
      </div>

      <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Net revenue"
          value={formatMoney(summary.netRevenueMinor, summary.currencyCode)}
          hint={`${formatMoney(summary.grossMinor, summary.currencyCode)} gross`}
        />
        <StatCard
          label="Platform cut"
          value={formatMoney(summary.commissionMinor, summary.currencyCode)}
        />
        <StatCard
          label="Paid out"
          value={formatMoney(summary.paidOutMinor, summary.currencyCode)}
          hint={`${summary.payoutCount} payment${summary.payoutCount === 1 ? "" : "s"}`}
        />
        <StatCard
          label="Outstanding"
          value={formatMoney(summary.outstandingPayoutMinor, summary.currencyCode)}
          hint={`${unsettled.length} unsettled line${unsettled.length === 1 ? "" : "s"}`}
        />
      </div>

      {canManage && summary.outstandingPayoutMinor > 0 ? (
        <div className="mb-6">
          <Button variant="primary" onClick={() => setPaying(true)}>
            <T>Issue payment (</T>
            {formatMoney(summary.outstandingPayoutMinor, summary.currencyCode)})
          </Button>
        </div>
      ) : null}

      <h2 className="mb-2 text-sm font-semibold text-ink">
        <T>Order lines</T>
      </h2>
      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>
              <T>Order</T>
            </Th>
            <Th>
              <T>Item</T>
            </Th>
            <Th>
              <T>Qty</T>
            </Th>
            <Th>
              <T>Gross</T>
            </Th>
            <Th>
              <T>Refunded</T>
            </Th>
            <Th>
              <T>Net</T>
            </Th>
            <Th>
              <T>Status</T>
            </Th>
          </tr>
        </thead>
        {lines.length === 0 ? (
          <tbody>
            <tr>
              <Td colSpan={7}>
                <EmptyState title="No paid orders yet for this farm" />
              </Td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {lines.map((line) => (
              <tr key={line.orderItemId} className="border-t border-line">
                <Td>
                  <Link
                    to={`/orders/${line.orderId}`}
                    className="font-medium text-brand underline-offset-2 hover:underline"
                  >
                    {line.orderReference}
                  </Link>
                  <span className="block text-xs text-ink-muted">{formatDate(line.orderedAt)}</span>
                </Td>
                <Td>
                  {line.productName}
                  {line.variantName ? (
                    <span className="block text-xs text-ink-muted">{line.variantName}</span>
                  ) : null}
                </Td>
                <Td className="tabular-nums">{line.quantity}</Td>
                <Td className="tabular-nums">{formatMoney(line.grossMinor, line.currencyCode)}</Td>
                <Td className="tabular-nums">
                  {line.refundedMinor > 0
                    ? `− ${formatMoney(line.refundedMinor, line.currencyCode)}`
                    : "—"}
                </Td>
                <Td className="tabular-nums font-medium">
                  {formatMoney(line.netMinor, line.currencyCode)}
                </Td>
                <Td>
                  <StatusPill status={line.settled ? "paid" : "pending"} />
                </Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>

      <h2 className="mb-2 mt-8 text-sm font-semibold text-ink">
        <T>Payment history</T>
      </h2>
      <PayoutTable payouts={payouts} />

      {paying ? <IssuePaymentDialog farm={summary} onClose={() => setPaying(false)} /> : null}
    </div>
  );
}

function PayoutTable({ payouts }: { payouts: FarmPayout[] }) {
  return (
    <DataTableShell>
      <thead className="bg-canvas">
        <tr>
          <Th>
            <T>When</T>
          </Th>
          <Th>
            <T>Net revenue</T>
          </Th>
          <Th>
            <T>Cut</T>
          </Th>
          <Th>
            <T>Paid</T>
          </Th>
          <Th>
            <T>Lines</T>
          </Th>
          <Th>
            <T>Reference</T>
          </Th>
          <Th>
            <T>Recorded by</T>
          </Th>
        </tr>
      </thead>
      {payouts.length === 0 ? (
        <tbody>
          <tr>
            <Td colSpan={7}>
              <EmptyState title="No payments recorded yet" />
            </Td>
          </tr>
        </tbody>
      ) : (
        <tbody>
          {payouts.map((payout) => (
            <tr key={payout.id} className="border-t border-line">
              <Td className="text-ink-muted">{formatDateTime(payout.createdAt)}</Td>
              <Td className="tabular-nums">
                {formatMoney(payout.netRevenueMinor, payout.currencyCode)}
              </Td>
              <Td className="tabular-nums">
                {formatMoney(payout.commissionMinor, payout.currencyCode)}
                <span className="block text-xs text-ink-muted">
                  {formatPercent(payout.commissionPercent)}
                </span>
              </Td>
              <Td className="tabular-nums font-medium">
                {formatMoney(payout.payoutMinor, payout.currencyCode)}
              </Td>
              <Td className="tabular-nums">{payout.itemCount}</Td>
              <Td className="font-mono text-xs">{payout.reference || "—"}</Td>
              <Td className="text-ink-muted">{payout.createdByName}</Td>
            </tr>
          ))}
        </tbody>
      )}
    </DataTableShell>
  );
}
