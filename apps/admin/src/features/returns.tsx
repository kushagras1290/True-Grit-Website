/** Return requests (RMA): customers file these from their order history on
 * the storefront; staff with `returns.manage` triage and resolve them here.
 * A refund resolution also requires `orders.refund` (checked server-side). */

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
  PageHeader,
  Pagination,
  SearchBox,
  Select,
  StatusPill,
  Td,
  Textarea,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import { formatDateTime, formatMoney } from "../lib/format";
import { PermissionGate } from "../lib/permissions";
import { T } from "../lib/i18n";

const REASON_LABELS: Record<string, string> = {
  damaged: "Damaged",
  wrong_item: "Wrong item",
  quality_issue: "Quality issue",
  not_as_described: "Not as described",
  missing_item: "Missing item",
  other: "Other",
};

export function ReturnsListPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const limit = 25;
  const offset = (page - 1) * limit;
  const { data, isLoading } = useQuery({
    queryKey: ["admin-returns", statusFilter, searchQuery, page],
    queryFn: () =>
      api.returns({
        status: statusFilter || undefined,
        limit,
        offset,
        search: searchQuery || undefined,
      }),
  });
  const returns = data ?? [];

  return (
    <div>
      <PageHeader
        title="Returns"
        description="Customer-filed return requests, from request through resolution."
        actions={
          <Select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setPage(1);
            }}
          >
            <option value="">
              <T>All statuses</T>
            </option>
            <option value="requested">
              <T>Requested</T>
            </option>
            <option value="under_review">
              <T>Under review</T>
            </option>
            <option value="approved">
              <T>Approved</T>
            </option>
            <option value="rejected">
              <T>Rejected</T>
            </option>
            <option value="refunded">
              <T>Refunded</T>
            </option>
            <option value="replaced">
              <T>Replaced</T>
            </option>
            <option value="completed">
              <T>Completed</T>
            </option>
          </Select>
        }
      />
      <div className="mb-4 max-w-sm">
        <SearchBox
          value={searchQuery}
          onSearch={(value) => {
            setSearchQuery(value);
            setPage(1);
          }}
          placeholder="Search by order reference or product..."
          aria-label="Search returns"
        />
      </div>
      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>
              <T>Order</T>
            </Th>
            <Th>
              <T>Customer</T>
            </Th>
            <Th>
              <T>Reason</T>
            </Th>
            <Th>
              <T>Status</T>
            </Th>
            <Th>
              <T>Requested</T>
            </Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={5} />
        ) : returns.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={5} className="px-3 py-8">
                <EmptyState
                  title="No return requests"
                  hint="Requests filed from the storefront appear here."
                />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {returns.map((entry) => (
              <tr key={entry.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <Link
                    to={`/returns/${entry.id}`}
                    className="font-medium text-brand hover:underline"
                  >
                    {entry.orderReference}
                  </Link>
                </Td>
                <Td className="text-ink-muted">{entry.customerName}</Td>
                <Td>{REASON_LABELS[entry.reasonCode] ?? entry.reasonCode}</Td>
                <Td>
                  <StatusPill status={entry.status} />
                </Td>
                <Td>{formatDateTime(entry.requestedAt)}</Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      <Pagination page={page} onPageChange={setPage} rowCount={returns.length} limit={limit} />
    </div>
  );
}

export function ReturnDetailPage() {
  const { id = "" } = useParams();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [resolutionType, setResolutionType] = useState<
    "refund" | "replacement" | "store_credit" | "none"
  >("refund");
  const [resolutionAmount, setResolutionAmount] = useState("");
  const [resolutionNotes, setResolutionNotes] = useState("");

  const {
    data: entry,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["admin-return", id],
    queryFn: () => api.getReturn(id),
    retry: false,
  });

  function invalidate() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin-return", id] }),
      queryClient.invalidateQueries({ queryKey: ["admin-returns"] }),
    ]);
  }

  const decideMutation = useMutation({
    mutationFn: (decision: string) => api.decideReturn(id, decision),
    onSuccess: async () => {
      await invalidate();
      toast.success("Return request updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update."),
  });

  const resolveMutation = useMutation({
    mutationFn: () =>
      api.resolveReturn(id, {
        resolutionType,
        resolutionAmountMinor:
          resolutionType === "refund" && resolutionAmount
            ? Math.round(Number(resolutionAmount) * 100)
            : undefined,
        resolutionNotes: resolutionNotes || undefined,
      }),
    onSuccess: async () => {
      await invalidate();
      toast.success("Return resolved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not resolve."),
  });

  if (isLoading)
    return (
      <p className="text-sm text-ink-muted">
        <T>Loading return request…</T>
      </p>
    );
  if (isError || !entry) return <EmptyState title="Return request not found" />;

  return (
    <div>
      <PageHeader
        title={`Return — ${entry.orderReference}`}
        description={entry.customerName}
        actions={<StatusPill status={entry.status} />}
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-4">
          <div className="rounded-md border border-line bg-surface p-5">
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-ink-muted">
                  <T>Reason</T>
                </dt>
                <dd className="font-medium text-ink">
                  {REASON_LABELS[entry.reasonCode] ?? entry.reasonCode}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">
                  <T>Product</T>
                </dt>
                <dd className="font-medium text-ink">
                  {entry.productName ?? <T>{"Whole order"}</T>}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">
                  <T>Order total</T>
                </dt>
                <dd className="font-medium text-ink">
                  {formatMoney(entry.orderTotalMinor, entry.currencyCode)}
                </dd>
              </div>
              <div>
                <dt className="text-ink-muted">
                  <T>Requested refund</T>
                </dt>
                <dd className="font-medium text-ink">
                  {entry.requestedRefundAmountMinor != null
                    ? formatMoney(entry.requestedRefundAmountMinor, entry.currencyCode)
                    : "—"}
                </dd>
              </div>
            </dl>
            <div className="mt-4">
              <p className="text-ink-muted">
                <T>Description</T>
              </p>
              <p className="mt-1 text-sm text-ink">{entry.description}</p>
            </div>
          </div>

          {(["refunded", "replaced", "completed"] as string[]).includes(entry.status) ? (
            <div className="rounded-md border border-line bg-surface p-5">
              <h2 className="font-display text-lg text-ink">
                <T>Resolution</T>
              </h2>
              <dl className="mt-3 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-ink-muted">
                    <T>Type</T>
                  </dt>
                  <dd className="font-medium text-ink">{entry.resolutionType ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-ink-muted">
                    <T>Amount</T>
                  </dt>
                  <dd className="font-medium text-ink">
                    {entry.resolutionAmountMinor != null
                      ? formatMoney(entry.resolutionAmountMinor, entry.currencyCode)
                      : "—"}
                  </dd>
                </div>
              </dl>
              {entry.resolutionNotes ? (
                <p className="mt-3 text-sm text-ink-muted">{entry.resolutionNotes}</p>
              ) : null}
            </div>
          ) : null}
        </div>

        <PermissionGate permission="returns.manage">
          <aside className="space-y-4 rounded-md border border-line bg-surface p-5">
            {entry.status === "requested" || entry.status === "under_review" ? (
              <div className="space-y-2">
                <h2 className="font-display text-base text-ink">
                  <T>Triage</T>
                </h2>
                {entry.status === "requested" ? (
                  <Button
                    className="w-full"
                    onClick={() => decideMutation.mutate("under_review")}
                    disabled={decideMutation.isPending}
                  >
                    <T>Mark under review</T>
                  </Button>
                ) : null}
                <Button
                  className="w-full"
                  variant="primary"
                  onClick={() => decideMutation.mutate("approved")}
                  disabled={decideMutation.isPending}
                >
                  <T>Approve</T>
                </Button>
                <Button
                  className="w-full"
                  variant="destructive"
                  onClick={() => decideMutation.mutate("rejected")}
                  disabled={decideMutation.isPending}
                >
                  <T>Reject</T>
                </Button>
              </div>
            ) : null}

            {entry.status === "approved" ? (
              <div className="space-y-3">
                <h2 className="font-display text-base text-ink">
                  <T>Resolve</T>
                </h2>
                <Field label="Resolution" htmlFor="ret-resolution-type">
                  <Select
                    id="ret-resolution-type"
                    value={resolutionType}
                    onChange={(event) =>
                      setResolutionType(event.target.value as typeof resolutionType)
                    }
                  >
                    <option value="refund">
                      <T>Refund</T>
                    </option>
                    <option value="replacement">
                      <T>Replacement</T>
                    </option>
                    <option value="store_credit">
                      <T>Store credit</T>
                    </option>
                    <option value="none">
                      <T>No action</T>
                    </option>
                  </Select>
                </Field>
                {resolutionType === "refund" ? (
                  <Field label="Refund amount (₹)" htmlFor="ret-resolution-amount">
                    <Input
                      id="ret-resolution-amount"
                      type="number"
                      min={0}
                      step="0.01"
                      value={resolutionAmount}
                      onChange={(event) => setResolutionAmount(event.target.value)}
                    />
                  </Field>
                ) : null}
                <Field label="Notes" htmlFor="ret-resolution-notes">
                  <Textarea
                    id="ret-resolution-notes"
                    rows={3}
                    value={resolutionNotes}
                    onChange={(event) => setResolutionNotes(event.target.value)}
                  />
                </Field>
                <Button
                  className="w-full"
                  variant="primary"
                  disabled={resolveMutation.isPending}
                  onClick={() => resolveMutation.mutate()}
                >
                  {resolveMutation.isPending ? <T>{"Resolving…"}</T> : <T>{"Resolve return"}</T>}
                </Button>
              </div>
            ) : null}
          </aside>
        </PermissionGate>
      </div>
    </div>
  );
}
