/** Subscribe & Save (migration 0064): support/oversight for customer
 * subscriptions, plus the renewal job's manual twin. Subscriptions are never
 * created here -- they only ever start from a customer's own product-page
 * action (see api/storefront.py) -- this page can only pause, resume and
 * cancel one on a customer's behalf, and run the identical renewal batch the
 * Cron Trigger runs on its own schedule.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  Button,
  DataTableShell,
  EmptyState,
  LoadingRows,
  PageHeader,
  Pagination,
  Select,
  StatusPill,
  Td,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import { formatDate, formatMoney } from "../lib/format";
import { usePermissions } from "../lib/permissions";

const STATUS_OPTIONS = ["active", "paused", "cancelled"];
const FREQUENCY_LABELS: Record<string, string> = {
  weekly: "Weekly",
  biweekly: "Every 2 weeks",
  monthly: "Monthly",
};

export function SubscriptionsListPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const canManage = permissions.has("subscriptions.manage");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const limit = 25;
  const offset = (page - 1) * limit;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-subscriptions", statusFilter, page],
    queryFn: () => api.subscriptions({ status: statusFilter || undefined, limit, offset }),
  });
  const rows = data?.items ?? [];

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["admin-subscriptions"] });
  }

  const pauseMutation = useMutation({
    mutationFn: (id: string) => api.pauseSubscription(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Subscription paused.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not pause the subscription."),
  });

  const resumeMutation = useMutation({
    mutationFn: (id: string) => api.resumeSubscription(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Subscription resumed.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not resume the subscription."),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api.cancelSubscription(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Subscription cancelled.");
    },
    onError: (error) =>
      toast.error(
        error instanceof ApiError ? error.message : "Could not cancel the subscription.",
      ),
  });

  const runRenewalsMutation = useMutation({
    mutationFn: () => api.runSubscriptionRenewals(),
    onSuccess: async (result) => {
      await invalidate();
      toast.success(
        result.processed === 0
          ? "No renewals were due."
          : `${result.succeeded} of ${result.processed} due renewal${result.processed === 1 ? "" : "s"} placed.`,
      );
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not run renewals."),
  });

  const busy =
    pauseMutation.isPending || resumeMutation.isPending || cancelMutation.isPending;

  return (
    <div>
      <PageHeader
        title="Subscriptions"
        description="Customer-created Subscribe & Save deliveries. Pause, resume or cancel on a customer's behalf, or run the renewal batch that otherwise fires on its own schedule."
        actions={
          canManage ? (
            <Button
              variant="secondary"
              disabled={runRenewalsMutation.isPending}
              onClick={() => runRenewalsMutation.mutate()}
            >
              {runRenewalsMutation.isPending ? "Running..." : "Run renewals now"}
            </Button>
          ) : undefined
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <Select
          value={statusFilter}
          onChange={(event) => {
            setStatusFilter(event.target.value);
            setPage(1);
          }}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
      </div>

      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Product</Th>
            <Th>Customer</Th>
            <Th>Frequency</Th>
            <Th>Status</Th>
            <Th>Next delivery</Th>
            {canManage ? <Th>Actions</Th> : null}
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={canManage ? 6 : 5} />
        ) : rows.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={canManage ? 6 : 5} className="px-3 py-8">
                <EmptyState
                  title="No subscriptions yet"
                  hint="These are created by customers from a product page, once Subscribe & Save is switched on in Site Settings."
                />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {rows.map((entry) => (
              <tr key={entry.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <p className="font-medium text-ink">{entry.productName}</p>
                  <p className="text-xs text-ink-muted">
                    {entry.quantity} × {entry.variantName}
                    {entry.unitPriceMinor !== null
                      ? ` · ${formatMoney(entry.unitPriceMinor, "INR")} each`
                      : ""}
                  </p>
                </Td>
                <Td>
                  <p className="text-ink">{entry.customerName ?? "—"}</p>
                  <p className="text-xs text-ink-muted">{entry.customerEmail ?? ""}</p>
                </Td>
                <Td>{FREQUENCY_LABELS[entry.frequency] ?? entry.frequency}</Td>
                <Td>
                  <StatusPill status={entry.status} />
                </Td>
                <Td>{entry.status === "cancelled" ? "—" : formatDate(entry.nextOrderDate)}</Td>
                {canManage ? (
                  <Td>
                    <div className="flex flex-wrap gap-2">
                      {entry.status === "active" ? (
                        <Button
                          variant="secondary"
                          disabled={busy}
                          onClick={() => pauseMutation.mutate(entry.id)}
                        >
                          Pause
                        </Button>
                      ) : null}
                      {entry.status === "paused" ? (
                        <Button
                          variant="secondary"
                          disabled={busy}
                          onClick={() => resumeMutation.mutate(entry.id)}
                        >
                          Resume
                        </Button>
                      ) : null}
                      {entry.status !== "cancelled" ? (
                        <Button
                          variant="destructive"
                          disabled={busy}
                          onClick={() => cancelMutation.mutate(entry.id)}
                        >
                          Cancel
                        </Button>
                      ) : null}
                    </div>
                  </Td>
                ) : null}
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      <Pagination page={page} onPageChange={setPage} rowCount={rows.length} limit={limit} />
    </div>
  );
}
