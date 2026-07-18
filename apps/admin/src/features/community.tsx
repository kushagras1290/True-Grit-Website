/** Community discussions: signed-in customers start threads and comment on
 * the storefront (`/community`); staff with `discussions.moderate` can hide,
 * restore, archive or permanently delete any thread or comment here, and
 * `settings.community` controls how long an account must exist before it can
 * start a new discussion (anyone signed in may still comment). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
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

function CommunitySettingsPanel() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["community-settings"], queryFn: api.communitySettings });
  const [months, setMonths] = useState("");

  useEffect(() => {
    if (data) setMonths(String(data.minAccountAgeMonths));
  }, [data]);

  const mutation = useMutation({
    mutationFn: (value: number) => api.updateCommunitySettings(value),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["community-settings"] });
      setMonths(String(result.minAccountAgeMonths));
      toast.success("Community settings saved.");
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not save."),
  });

  return (
    <PermissionGate permission="settings.community">
      <div className="mb-6 flex flex-wrap items-end gap-3 rounded-md border border-line bg-surface p-4">
        <Field
          label="Minimum account age to start a discussion (months)"
          htmlFor="min-account-age"
        >
          <Input
            id="min-account-age"
            type="number"
            min={0}
            max={120}
            value={months}
            onChange={(event) => setMonths(event.target.value)}
            className="w-32"
          />
        </Field>
        <Button
          variant="secondary"
          disabled={mutation.isPending || months === ""}
          onClick={() => mutation.mutate(Math.max(0, Math.min(120, Number(months) || 0)))}
        >
          {mutation.isPending ? "Saving..." : "Save"}
        </Button>
        <p className="w-full text-xs text-ink-muted">
          Anyone signed in may comment. Only starting a new discussion is gated by account age.
        </p>
      </div>
    </PermissionGate>
  );
}

export function DiscussionsListPage() {
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const limit = 25;
  const offset = (page - 1) * limit;
  const { data, isLoading } = useQuery({
    queryKey: ["admin-discussions", statusFilter, searchQuery, page],
    queryFn: () =>
      api.discussions({
        status: statusFilter || undefined,
        limit,
        offset,
        search: searchQuery || undefined,
      }),
  });
  const discussions = data ?? [];

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">Community</h1>
          <p className="text-sm text-ink-muted">Discussions and comments started by customers.</p>
        </div>
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
          <option value="archived">Archived</option>
          <option value="removed">Removed</option>
        </Select>
      </div>

      <CommunitySettingsPanel />

      <div className="mb-4 max-w-sm">
        <SearchBox
          value={searchQuery}
          onSearch={(value) => {
            setSearchQuery(value);
            setPage(1);
          }}
          placeholder="Search by title or author..."
          aria-label="Search discussions"
        />
      </div>
      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Title</Th>
            <Th>Author</Th>
            <Th>Comments</Th>
            <Th>Status</Th>
            <Th>Last activity</Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={5} />
        ) : discussions.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={5} className="px-3 py-8">
                <EmptyState title="No discussions" hint="Threads started from the storefront appear here." />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {discussions.map((entry) => (
              <tr key={entry.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <Link to={`/community/${entry.id}`} className="font-medium text-brand hover:underline">
                    {entry.title}
                  </Link>
                </Td>
                <Td className="text-ink-muted">{entry.authorName}</Td>
                <Td>{entry.commentCount}</Td>
                <Td>
                  <StatusPill status={entry.status} />
                </Td>
                <Td>{formatDateTime(entry.lastActivityAt)}</Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      <Pagination page={page} onPageChange={setPage} rowCount={discussions.length} limit={limit} />
    </div>
  );
}

export function DiscussionDetailPage() {
  const { id = "" } = useParams();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");

  const {
    data: entry,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["admin-discussion", id],
    queryFn: () => api.getDiscussion(id),
    retry: false,
  });

  function invalidate() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin-discussion", id] }),
      queryClient.invalidateQueries({ queryKey: ["admin-discussions"] }),
    ]);
  }

  const moderateMutation = useMutation({
    mutationFn: (action: string) => api.moderateDiscussion(id, action, reason || undefined),
    onSuccess: async () => {
      await invalidate();
      toast.success("Discussion updated.");
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not update."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteDiscussion(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Discussion deleted.");
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not delete."),
  });

  const moderateCommentMutation = useMutation({
    mutationFn: (input: { commentId: string; action: string }) =>
      api.moderateComment(input.commentId, input.action),
    onSuccess: async () => {
      await invalidate();
      toast.success("Comment updated.");
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not update."),
  });

  const deleteCommentMutation = useMutation({
    mutationFn: (commentId: string) => api.deleteComment(commentId),
    onSuccess: async () => {
      await invalidate();
      toast.success("Comment deleted.");
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not delete."),
  });

  if (isLoading) return <p className="text-sm text-ink-muted">Loading discussion…</p>;
  if (isError || !entry) return <EmptyState title="Discussion not found" />;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">{entry.title}</h1>
          <p className="text-sm text-ink-muted">
            {entry.authorName} ({entry.authorEmail}) · started {formatDateTime(entry.createdAt)}
          </p>
        </div>
        <StatusPill status={entry.status} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-4">
          <div className="rounded-md border border-line bg-surface p-5">
            <p className="whitespace-pre-wrap text-sm text-ink">{entry.body}</p>
          </div>
          {entry.moderationReason ? (
            <div className="rounded-md border border-line bg-canvas p-5">
              <p className="text-ink-muted">Moderation reason</p>
              <p className="mt-1 text-sm text-ink">{entry.moderationReason}</p>
            </div>
          ) : null}

          <div>
            <h2 className="mb-2 font-display text-lg text-ink">Comments ({entry.comments.length})</h2>
            {entry.comments.length === 0 ? (
              <p className="text-sm text-ink-muted">No comments yet.</p>
            ) : (
              <ul className="space-y-3">
                {entry.comments.map((comment) => (
                  <li key={comment.id} className="rounded-md border border-line bg-surface p-4">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs text-ink-muted">
                        {comment.authorName} · {formatDateTime(comment.createdAt)}
                      </p>
                      <StatusPill status={comment.status} />
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-ink">{comment.body}</p>
                    {comment.moderationReason ? (
                      <p className="mt-1 text-xs text-ink-muted">Reason: {comment.moderationReason}</p>
                    ) : null}
                    <PermissionGate permission="discussions.moderate">
                      <div className="mt-3 flex flex-wrap gap-2">
                        {comment.status !== "visible" ? (
                          <Button
                            variant="secondary"
                            className="min-h-8 px-2.5 text-xs"
                            onClick={() =>
                              moderateCommentMutation.mutate({ commentId: comment.id, action: "restore" })
                            }
                            disabled={moderateCommentMutation.isPending}
                          >
                            Restore
                          </Button>
                        ) : (
                          <Button
                            variant="secondary"
                            className="min-h-8 px-2.5 text-xs"
                            onClick={() =>
                              moderateCommentMutation.mutate({ commentId: comment.id, action: "hide" })
                            }
                            disabled={moderateCommentMutation.isPending}
                          >
                            Hide
                          </Button>
                        )}
                        <Button
                          variant="destructive"
                          className="min-h-8 px-2.5 text-xs"
                          onClick={() => {
                            if (window.confirm("Permanently delete this comment?")) {
                              deleteCommentMutation.mutate(comment.id);
                            }
                          }}
                          disabled={deleteCommentMutation.isPending}
                        >
                          Delete
                        </Button>
                      </div>
                    </PermissionGate>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <PermissionGate permission="discussions.moderate">
          <aside className="h-fit space-y-3 rounded-md border border-line bg-surface p-5">
            <h2 className="font-display text-base text-ink">Moderate thread</h2>
            <Field label="Reason (optional)" htmlFor="moderation-reason">
              <Textarea
                id="moderation-reason"
                rows={2}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </Field>
            {entry.status === "visible" ? (
              <Button
                className="w-full"
                variant="secondary"
                onClick={() => moderateMutation.mutate("hide")}
                disabled={moderateMutation.isPending}
              >
                Hide
              </Button>
            ) : (
              <Button
                className="w-full"
                variant="secondary"
                onClick={() => moderateMutation.mutate("restore")}
                disabled={moderateMutation.isPending}
              >
                Restore (make visible)
              </Button>
            )}
            <Button
              className="w-full"
              variant="secondary"
              onClick={() => moderateMutation.mutate("archive")}
              disabled={moderateMutation.isPending || entry.status === "archived"}
            >
              Archive
            </Button>
            <Button
              className="w-full"
              variant="destructive"
              onClick={() => moderateMutation.mutate("remove")}
              disabled={moderateMutation.isPending || entry.status === "removed"}
            >
              Remove (soft)
            </Button>
            <Button
              className="w-full"
              variant="destructive"
              onClick={() => {
                if (window.confirm("Permanently delete this discussion and all its comments?")) {
                  deleteMutation.mutate();
                }
              }}
              disabled={deleteMutation.isPending}
            >
              Delete permanently
            </Button>
          </aside>
        </PermissionGate>
      </div>
    </div>
  );
}
