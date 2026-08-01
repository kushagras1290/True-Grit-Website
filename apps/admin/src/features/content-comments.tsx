/** Reader comments on published blog posts and recipes (`/blog/:slug`,
 * `/recipes/:slug`). Policed with `discussions.moderate` -- the same
 * permission as community threads -- rather than a parallel grant, since the
 * people who police one conversation stream police the other (migration
 * 0043).
 *
 * A comment is never edited here, only hidden (reversible, keeps the
 * evidence) or deleted (permanent, for content that must not persist). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import {
  Button,
  DataTableShell,
  EmptyState,
  LoadingRows,
  Pagination,
  SearchBox,
  Select,
  StatusPill,
  Td,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { usePermissions } from "../lib/permissions";

const CONTENT_TYPE_LABELS: Record<string, string> = {
  article: "Blog post",
  recipe: "Recipe",
};

const CONTENT_TYPE_PATH: Record<string, string> = {
  article: "/blog/",
  recipe: "/recipes/",
};

export function ContentCommentsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const canModerate = permissions.has("discussions.moderate");
  const [contentTypeFilter, setContentTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const limit = 25;
  const offset = (page - 1) * limit;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-content-comments", contentTypeFilter, statusFilter, searchQuery, page],
    queryFn: () =>
      api.contentComments({
        contentType: contentTypeFilter || undefined,
        status: statusFilter || undefined,
        search: searchQuery || undefined,
        limit,
        offset,
      }),
  });
  const comments = data?.items ?? [];

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["admin-content-comments"] });
  }

  const moderateMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) => {
      const reason =
        action === "hide"
          ? (prompt("Reason (shown only to staff, optional):") ?? undefined)
          : undefined;
      return api.moderateContentComment(id, action, reason || undefined);
    },
    onSuccess: async () => {
      await invalidate();
      toast.success("Comment updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteContentComment(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Comment deleted.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete."),
  });

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">Post Comments</h1>
          <p className="text-sm text-ink-muted">
            Reader comments on blog posts and recipes.
            {data && !data.enabled ? (
              <span className="ml-1 text-danger">
                Commenting is currently switched off site-wide.
              </span>
            ) : null}
          </p>
        </div>
        <div className="flex gap-2">
          <Select
            value={contentTypeFilter}
            onChange={(event) => {
              setContentTypeFilter(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All types</option>
            <option value="article">Blog posts</option>
            <option value="recipe">Recipes</option>
          </Select>
          <Select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            <option value="visible">Visible</option>
            <option value="hidden">Hidden</option>
            <option value="removed">Removed</option>
          </Select>
        </div>
      </div>

      <div className="mb-4 max-w-sm">
        <SearchBox
          value={searchQuery}
          onSearch={(value) => {
            setSearchQuery(value);
            setPage(1);
          }}
          placeholder="Search by comment text or author name..."
          aria-label="Search comments"
        />
      </div>

      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Comment</Th>
            <Th>On</Th>
            <Th>Author</Th>
            <Th>Status</Th>
            <Th>Posted</Th>
            {canModerate ? <Th>Actions</Th> : null}
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={canModerate ? 6 : 5} />
        ) : comments.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={canModerate ? 6 : 5} className="px-3 py-8">
                <EmptyState
                  title="No comments"
                  hint="Reader comments on blog posts and recipes appear here."
                />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {comments.map((entry) => (
              <tr key={entry.id} className="border-t border-line hover:bg-canvas/60">
                <Td className="max-w-sm">
                  <p className="line-clamp-2 text-ink">{entry.body}</p>
                  {entry.moderationReason ? (
                    <p className="mt-1 text-xs text-ink-muted">Reason: {entry.moderationReason}</p>
                  ) : null}
                </Td>
                <Td>
                  <Link
                    to={`${CONTENT_TYPE_PATH[entry.contentType]}${entry.parentSlug}`}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-brand hover:underline"
                  >
                    {entry.parentTitle}
                  </Link>
                  <span className="block text-xs text-ink-muted">
                    {CONTENT_TYPE_LABELS[entry.contentType] ?? entry.contentType}
                  </span>
                </Td>
                <Td>
                  {entry.authorName}
                  {entry.authorEmail ? (
                    <span className="block text-xs text-ink-muted">{entry.authorEmail}</span>
                  ) : null}
                </Td>
                <Td>
                  <StatusPill status={entry.status} />
                </Td>
                <Td>{formatDateTime(entry.createdAt)}</Td>
                {canModerate ? (
                  <Td>
                    <div className="flex flex-wrap gap-2">
                      {entry.status !== "visible" ? (
                        <Button
                          variant="secondary"
                          onClick={() =>
                            moderateMutation.mutate({ id: entry.id, action: "restore" })
                          }
                          disabled={moderateMutation.isPending}
                        >
                          Restore
                        </Button>
                      ) : (
                        <Button
                          variant="secondary"
                          onClick={() => moderateMutation.mutate({ id: entry.id, action: "hide" })}
                          disabled={moderateMutation.isPending}
                        >
                          Hide
                        </Button>
                      )}
                      <Button
                        variant="destructive"
                        onClick={() => {
                          if (confirm("Permanently delete this comment? This cannot be undone.")) {
                            deleteMutation.mutate(entry.id);
                          }
                        }}
                        disabled={deleteMutation.isPending}
                      >
                        Delete
                      </Button>
                    </div>
                  </Td>
                ) : null}
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      <Pagination page={page} onPageChange={setPage} rowCount={comments.length} limit={limit} />
    </div>
  );
}
