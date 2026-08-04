/** Farm partnership applications: growers apply from the storefront
 * (`/farms/partner`, no account required) to supply the marketplace; staff
 * with `farm_requests.review` triage the pipeline here.
 *
 * Approval records a decision and emails the applicant -- it does NOT create
 * a `farms` row. Onboarding (contracts, certification, pricing) happens
 * off-system; `linkFarmRequestToFarm` exists only to record, after the fact,
 * which `farms` row an approved application became. See migration 0044 for
 * the full reasoning.
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
import { formatDateTime } from "../lib/format";
import { PermissionGate } from "../lib/permissions";
import { T } from "../lib/i18n";

const STATUS_LABELS: Record<string, string> = {
  submitted: "Submitted",
  under_review: "Under review",
  contacted: "Contacted",
  approved: "Approved",
  rejected: "Rejected",
};

const OPEN_STATUSES = new Set(["submitted", "under_review", "contacted"]);

export function FarmRequestsListPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const limit = 25;
  const offset = (page - 1) * limit;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin-farm-requests", statusFilter, searchQuery, page],
    queryFn: () =>
      api.farmRequests({
        status: statusFilter || undefined,
        search: searchQuery || undefined,
        limit,
        offset,
      }),
  });
  const requests = data?.items ?? [];

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">
            <T>Farm Requests</T>
          </h1>
          <p className="text-sm text-ink-muted">
            <T>
              Growers who applied at /farms/partner to supply the market. No account is required to
              apply, so review here is the only gate.
            </T>
          </p>
        </div>
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
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </div>

      {isError ? (
        <EmptyState
          title="Farm requests unavailable"
          hint="Only main admins can review farm applications."
        />
      ) : (
        <>
          <div className="mb-4 max-w-sm">
            <SearchBox
              value={searchQuery}
              onSearch={(value) => {
                setSearchQuery(value);
                setPage(1);
              }}
              placeholder="Search by farm, name, email or phone..."
              aria-label="Search farm requests"
            />
          </div>
          <DataTableShell>
            <thead className="bg-canvas">
              <tr>
                <Th>
                  <T>Farm</T>
                </Th>
                <Th>
                  <T>Region</T>
                </Th>
                <Th>
                  <T>Applicant</T>
                </Th>
                <Th>
                  <T>Status</T>
                </Th>
                <Th>
                  <T>Submitted</T>
                </Th>
              </tr>
            </thead>
            {isLoading ? (
              <LoadingRows columns={5} />
            ) : requests.length === 0 ? (
              <tbody>
                <tr>
                  <td colSpan={5} className="px-3 py-8">
                    <EmptyState
                      title="No farm requests"
                      hint="Applications from the storefront's partnership form appear here."
                    />
                  </td>
                </tr>
              </tbody>
            ) : (
              <tbody>
                {requests.map((entry) => (
                  <tr key={entry.id} className="border-t border-line hover:bg-canvas/60">
                    <Td>
                      <Link
                        to={`/farm-requests/${entry.id}`}
                        className="font-medium text-brand hover:underline"
                      >
                        {entry.farmName}
                      </Link>
                    </Td>
                    <Td className="text-ink-muted">
                      {entry.region}
                      {entry.state ? `, ${entry.state}` : ""}
                    </Td>
                    <Td>
                      {entry.contactName}
                      <span className="block text-xs text-ink-muted">
                        {entry.contactPhone} · {entry.contactEmail}
                      </span>
                    </Td>
                    <Td>
                      <StatusPill status={entry.status} />
                    </Td>
                    <Td>{formatDateTime(entry.createdAt)}</Td>
                  </tr>
                ))}
              </tbody>
            )}
          </DataTableShell>
          <Pagination page={page} onPageChange={setPage} rowCount={requests.length} limit={limit} />
        </>
      )}
    </div>
  );
}

export function FarmRequestDetailPage() {
  const { id = "" } = useParams();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [farmId, setFarmId] = useState("");

  const {
    data: entry,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["admin-farm-request", id],
    queryFn: () => api.getFarmRequest(id),
    retry: false,
  });

  function invalidate() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin-farm-request", id] }),
      queryClient.invalidateQueries({ queryKey: ["admin-farm-requests"] }),
      queryClient.invalidateQueries({ queryKey: ["farm-requests-open-count"] }),
    ]);
  }

  const decideMutation = useMutation({
    mutationFn: (decision: string) => api.decideFarmRequest(id, decision, note || undefined),
    onSuccess: async (result) => {
      await invalidate();
      setNote("");
      toast.success(
        result.status === "approved"
          ? "Application approved. The grower has been emailed."
          : result.status === "rejected"
            ? "Application declined. The grower has been emailed."
            : "Application updated.",
      );
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update."),
  });

  const linkMutation = useMutation({
    mutationFn: () => api.linkFarmRequestToFarm(id, farmId.trim()),
    onSuccess: async () => {
      await invalidate();
      setFarmId("");
      toast.success("Linked to the farm record.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not link the farm."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteFarmRequest(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-farm-requests"] });
      toast.success("Application deleted.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete."),
  });

  if (isLoading)
    return (
      <p className="text-sm text-ink-muted">
        <T>Loading application…</T>
      </p>
    );
  if (isError || !entry) return <EmptyState title="Farm request not found" />;

  const isOpen = OPEN_STATUSES.has(entry.status);
  const rejectNeedsNote = true; // enforced server-side too

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">{entry.farmName}</h1>
          <p className="text-sm text-ink-muted">
            {entry.region}
            {entry.state ? `, ${entry.state}` : ""} <T>· applied by</T> {entry.contactName} (
            {entry.contactPhone}, {entry.contactEmail})
          </p>
        </div>
        <StatusPill status={entry.status} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-4">
          <div className="rounded-md border border-line bg-surface p-5">
            <p className="text-ink-muted">
              <T>Message from the applicant</T>
            </p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{entry.message}</p>
          </div>

          <div className="rounded-md border border-line bg-surface p-5">
            <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-ink-muted">
                  <T>City / town</T>
                </dt>
                <dd className="font-medium text-ink">{entry.city || "—"}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">
                  <T>PIN code</T>
                </dt>
                <dd className="font-medium text-ink">{entry.pincode || "—"}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">
                  <T>Established</T>
                </dt>
                <dd className="font-medium text-ink">{entry.establishedYear ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">
                  <T>Land under cultivation</T>
                </dt>
                <dd className="font-medium text-ink">{entry.landAreaAcres || "—"}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">
                  <T>Certification</T>
                </dt>
                <dd className="font-medium text-ink">{entry.certification || "—"}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">
                  <T>Website</T>
                </dt>
                <dd className="font-medium text-ink">
                  {entry.websiteUrl ? (
                    <a
                      href={entry.websiteUrl}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="text-brand hover:underline"
                    >
                      {entry.websiteUrl}
                    </a>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
            </dl>
            {entry.primaryProduce ? (
              <p className="mt-4 text-sm">
                <span className="text-ink-muted">
                  <T>What they grow:</T>{" "}
                </span>
                <span className="text-ink">{entry.primaryProduce}</span>
              </p>
            ) : null}
            {entry.farmingPractices ? (
              <p className="mt-2 text-sm">
                <span className="text-ink-muted">
                  <T>Farming practices:</T>{" "}
                </span>
                <span className="text-ink">{entry.farmingPractices}</span>
              </p>
            ) : null}
          </div>

          {entry.reviewerNotes ? (
            <div className="rounded-md border border-line bg-canvas p-5">
              <p className="text-ink-muted">
                <T>Reviewer note</T>
                {entry.reviewerName ? ` — ${entry.reviewerName}` : ""}
              </p>
              <p className="mt-1 text-sm text-ink">{entry.reviewerNotes}</p>
            </div>
          ) : null}

          {entry.submitterName ? (
            <p className="text-sm text-ink-muted">
              <T>Submitted while signed in as</T> {entry.submitterName}.
            </p>
          ) : null}

          {entry.status === "approved" ? (
            <div className="rounded-md border border-line bg-surface p-5">
              <p className="text-ink-muted">
                <T>Farm record</T>
              </p>
              {entry.linkedFarmName ? (
                <p className="mt-1 text-sm text-ink">
                  <T>Linked to</T> <span className="font-medium">{entry.linkedFarmName}</span>.
                </p>
              ) : (
                <PermissionGate permission="farm_requests.review">
                  <p className="mt-1 text-sm text-ink-muted">
                    <T>
                      Once you have created this grower's farm in the console, link the application
                      to it here for provenance.
                    </T>
                  </p>
                  <div className="mt-3 flex gap-2">
                    <Input
                      value={farmId}
                      onChange={(event) => setFarmId(event.target.value)}
                      placeholder="Farm id (e.g. farm_devika)"
                    />
                    <Button
                      variant="secondary"
                      disabled={!farmId.trim() || linkMutation.isPending}
                      onClick={() => linkMutation.mutate()}
                    >
                      <T>Link</T>
                    </Button>
                  </div>
                </PermissionGate>
              )}
            </div>
          ) : null}
        </div>

        <PermissionGate permission="farm_requests.review">
          <aside className="h-fit space-y-3 rounded-md border border-line bg-surface p-5">
            <h2 className="font-display text-base text-ink">
              <T>Decision</T>
            </h2>
            {isOpen ? (
              <>
                {entry.status === "submitted" ? (
                  <Button
                    className="w-full"
                    variant="secondary"
                    onClick={() => decideMutation.mutate("under_review")}
                    disabled={decideMutation.isPending}
                  >
                    <T>Mark under review</T>
                  </Button>
                ) : null}
                {entry.status !== "contacted" ? (
                  <Button
                    className="w-full"
                    variant="secondary"
                    onClick={() => decideMutation.mutate("contacted")}
                    disabled={decideMutation.isPending}
                  >
                    <T>Mark contacted</T>
                  </Button>
                ) : null}
                <Field label="Note (required to decline)" htmlFor="farm-request-note">
                  <Textarea
                    id="farm-request-note"
                    rows={3}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    placeholder="Visit notes, or the reason for declining — emailed to the applicant on approve/reject."
                  />
                </Field>
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
                  disabled={decideMutation.isPending || (rejectNeedsNote && !note.trim())}
                >
                  <T>Decline</T>
                </Button>
              </>
            ) : (
              <p className="text-sm text-ink-muted">
                <T>This application is</T> {STATUS_LABELS[entry.status]?.toLowerCase()}{" "}
                <T>and cannot be re-decided.</T>
              </p>
            )}
            <div className="border-t border-line pt-3">
              <Button
                className="w-full"
                variant="destructive"
                onClick={() => {
                  if (
                    confirm(`Delete the application from ${entry.farmName}? This cannot be undone.`)
                  ) {
                    deleteMutation.mutate();
                  }
                }}
                disabled={deleteMutation.isPending}
              >
                <T>Delete (spam)</T>
              </Button>
            </div>
          </aside>
        </PermissionGate>
      </div>
    </div>
  );
}
