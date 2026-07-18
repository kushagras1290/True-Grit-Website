/** Community blog/recipe submissions: visitors pitch a post or recipe from
 * the storefront (signed in, so every submission is tied to a real account);
 * staff with `submissions.review` approve (published immediately — no
 * separate publish step), reject, or request changes. Approving promotes the
 * submission straight into Blog/Recipes. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  Button,
  DataTableShell,
  EmptyState,
  Field,
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

const CONTENT_TYPE_LABELS: Record<string, string> = {
  article: "Blog post",
  recipe: "Recipe",
};

export function SubmissionsListPage() {
  const [contentTypeFilter, setContentTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const limit = 25;
  const offset = (page - 1) * limit;
  const { data, isLoading } = useQuery({
    queryKey: ["admin-submissions", contentTypeFilter, statusFilter, searchQuery, page],
    queryFn: () =>
      api.submissions({
        contentType: contentTypeFilter || undefined,
        status: statusFilter || undefined,
        limit,
        offset,
        search: searchQuery || undefined,
      }),
  });
  const submissions = data ?? [];

  return (
    <div>
      <PageHeaderWithFilters
        contentTypeFilter={contentTypeFilter}
        setContentTypeFilter={(value) => {
          setContentTypeFilter(value);
          setPage(1);
        }}
        statusFilter={statusFilter}
        setStatusFilter={(value) => {
          setStatusFilter(value);
          setPage(1);
        }}
      />
      <div className="mb-4 max-w-sm">
        <SearchBox
          value={searchQuery}
          onSearch={(value) => {
            setSearchQuery(value);
            setPage(1);
          }}
          placeholder="Search by title, name or email..."
          aria-label="Search submissions"
        />
      </div>
      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Title</Th>
            <Th>Type</Th>
            <Th>Submitted by</Th>
            <Th>Status</Th>
            <Th>Submitted</Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={5} />
        ) : submissions.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={5} className="px-3 py-8">
                <EmptyState
                  title="No submissions"
                  hint="Blog and recipe pitches from the community appear here."
                />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {submissions.map((entry) => (
              <tr key={entry.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <Link
                    to={`/submissions/${entry.id}`}
                    className="font-medium text-brand hover:underline"
                  >
                    {entry.title}
                  </Link>
                </Td>
                <Td className="text-ink-muted">{CONTENT_TYPE_LABELS[entry.contentType] ?? entry.contentType}</Td>
                <Td className="text-ink-muted">
                  {entry.contactName}
                  <span className="block text-xs">{entry.contactEmail}</span>
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
      <Pagination page={page} onPageChange={setPage} rowCount={submissions.length} limit={limit} />
    </div>
  );
}

function PageHeaderWithFilters({
  contentTypeFilter,
  setContentTypeFilter,
  statusFilter,
  setStatusFilter,
}: {
  contentTypeFilter: string;
  setContentTypeFilter: (value: string) => void;
  statusFilter: string;
  setStatusFilter: (value: string) => void;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="font-display text-2xl text-ink">Submissions</h1>
        <p className="text-sm text-ink-muted">
          Blog posts and recipes pitched by the community, awaiting review.
        </p>
      </div>
      <div className="flex gap-2">
        <Select value={contentTypeFilter} onChange={(event) => setContentTypeFilter(event.target.value)}>
          <option value="">All types</option>
          <option value="article">Blog posts</option>
          <option value="recipe">Recipes</option>
        </Select>
        <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="">All statuses</option>
          <option value="submitted">Submitted</option>
          <option value="under_review">Under review</option>
          <option value="changes_requested">Changes requested</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </Select>
      </div>
    </div>
  );
}

export function SubmissionDetailPage() {
  const { id = "" } = useParams();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");

  const {
    data: entry,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["admin-submission", id],
    queryFn: () => api.getSubmission(id),
    retry: false,
  });

  function invalidate() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin-submission", id] }),
      queryClient.invalidateQueries({ queryKey: ["admin-submissions"] }),
      queryClient.invalidateQueries({ queryKey: ["submissions-pending-count"] }),
    ]);
  }

  const decideMutation = useMutation({
    mutationFn: (decision: string) => api.decideSubmission(id, decision, note || undefined),
    onSuccess: async (result) => {
      await invalidate();
      setNote("");
      toast.success(
        result.status === "approved"
          ? "Submission approved and published."
          : "Submission updated.",
      );
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not update."),
  });

  if (isLoading) return <p className="text-sm text-ink-muted">Loading submission…</p>;
  if (isError || !entry) return <EmptyState title="Submission not found" />;

  const needsNote = true; // reject/changes both need a note; enforced server-side too
  const isOpen = ["submitted", "under_review", "changes_requested"].includes(entry.status);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">{entry.title}</h1>
          <p className="text-sm text-ink-muted">
            {CONTENT_TYPE_LABELS[entry.contentType] ?? entry.contentType} · submitted by {entry.contactName} (
            {entry.contactEmail}
            {entry.contactPhone ? `, ${entry.contactPhone}` : ""})
          </p>
        </div>
        <StatusPill status={entry.status} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-4">
          {entry.excerpt ? (
            <div className="rounded-md border border-line bg-surface p-5">
              <p className="text-ink-muted">Excerpt</p>
              <p className="mt-1 text-sm text-ink">{entry.excerpt}</p>
            </div>
          ) : null}

          <div className="rounded-md border border-line bg-surface p-5">
            <p className="text-ink-muted">Body</p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{entry.body}</p>
          </div>

          {entry.contentType === "recipe" ? (
            <div className="rounded-md border border-line bg-surface p-5">
              <dl className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <dt className="text-ink-muted">Prep</dt>
                  <dd className="font-medium text-ink">{entry.prepMinutes ?? "—"} min</dd>
                </div>
                <div>
                  <dt className="text-ink-muted">Cook</dt>
                  <dd className="font-medium text-ink">{entry.cookMinutes ?? "—"} min</dd>
                </div>
                <div>
                  <dt className="text-ink-muted">Servings</dt>
                  <dd className="font-medium text-ink">{entry.servings ?? "—"}</dd>
                </div>
              </dl>
              {entry.dietaryTags.length > 0 ? (
                <p className="mt-3 text-xs text-ink-muted">Tags: {entry.dietaryTags.join(", ")}</p>
              ) : null}
              <div className="mt-4">
                <p className="text-ink-muted">Ingredients</p>
                <ul className="mt-1 list-inside list-disc text-sm text-ink">
                  {entry.ingredients.map((ingredient, index) => (
                    <li key={index}>
                      {ingredient.label}
                      {ingredient.quantityText ? ` — ${ingredient.quantityText}` : ""}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="mt-4">
                <p className="text-ink-muted">Steps</p>
                <ol className="mt-1 list-inside list-decimal text-sm text-ink">
                  {entry.steps.map((step, index) => (
                    <li key={index}>{step}</li>
                  ))}
                </ol>
              </div>
            </div>
          ) : null}

          {entry.reviewerNotes ? (
            <div className="rounded-md border border-line bg-canvas p-5">
              <p className="text-ink-muted">Last reviewer note</p>
              <p className="mt-1 text-sm text-ink">{entry.reviewerNotes}</p>
            </div>
          ) : null}

          {entry.status === "approved" ? (
            <p className="text-sm text-ink-muted">
              Published as{" "}
              <Link
                to={entry.contentType === "article" ? "/blog" : "/recipes"}
                className="text-brand hover:underline"
              >
                a live {CONTENT_TYPE_LABELS[entry.contentType]?.toLowerCase()}
              </Link>
              .
            </p>
          ) : null}
        </div>

        <PermissionGate permission="submissions.review">
          {isOpen ? (
            <aside className="h-fit space-y-3 rounded-md border border-line bg-surface p-5">
              <h2 className="font-display text-base text-ink">Decision</h2>
              {entry.status === "submitted" ? (
                <Button
                  className="w-full"
                  variant="secondary"
                  onClick={() => decideMutation.mutate("under_review")}
                  disabled={decideMutation.isPending}
                >
                  Mark under review
                </Button>
              ) : null}
              <Field label="Note (required to request changes or reject)" htmlFor="submission-note">
                <Textarea
                  id="submission-note"
                  rows={3}
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="Why are changes needed, or why was this declined?"
                />
              </Field>
              <Button
                className="w-full"
                variant="primary"
                onClick={() => decideMutation.mutate("approved")}
                disabled={decideMutation.isPending}
              >
                Approve &amp; publish
              </Button>
              <Button
                className="w-full"
                variant="secondary"
                onClick={() => decideMutation.mutate("changes_requested")}
                disabled={decideMutation.isPending || (needsNote && !note.trim())}
              >
                Request changes
              </Button>
              <Button
                className="w-full"
                variant="destructive"
                onClick={() => decideMutation.mutate("rejected")}
                disabled={decideMutation.isPending || (needsNote && !note.trim())}
              >
                Reject
              </Button>
            </aside>
          ) : null}
        </PermissionGate>
      </div>
    </div>
  );
}
