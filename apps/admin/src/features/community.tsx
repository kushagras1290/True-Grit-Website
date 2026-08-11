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
  ConfirmDialog,
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
        <Field label="Minimum account age to start a discussion (months)" htmlFor="min-account-age">
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
          {mutation.isPending ? <T>{"Saving..."}</T> : <T>{"Save"}</T>}
        </Button>
        <p className="w-full text-xs text-ink-muted">
          <T>
            Anyone signed in may comment. Only starting a new discussion is gated by account age.
          </T>
        </p>
      </div>
    </PermissionGate>
  );
}

export function DiscussionsListPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
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
  const [selectedDiscussionIds, setSelectedDiscussionIds] = useState<string[]>([]);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const allSelected =
    discussions.length > 0 &&
    discussions.every((discussion) => selectedDiscussionIds.includes(discussion.id));

  const deleteMutation = useMutation({
    mutationFn: (discussionIds: string[]) => api.deleteDiscussions(discussionIds),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["admin-discussions"] });
      setSelectedDiscussionIds([]);
      setConfirmingDelete(false);
      toast.success(`${result.count} discussion${result.count === 1 ? "" : "s"} deleted.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete the discussions."),
  });

  function toggleDiscussion(discussionId: string) {
    setSelectedDiscussionIds((current) =>
      current.includes(discussionId)
        ? current.filter((id) => id !== discussionId)
        : [...current, discussionId],
    );
  }

  function toggleAllDiscussions() {
    setSelectedDiscussionIds(allSelected ? [] : discussions.map((discussion) => discussion.id));
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">
            <T>Community</T>
          </h1>
          <p className="text-sm text-ink-muted">
            <T>Discussions and comments started by customers.</T>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <PermissionGate permission="discussions.moderate">
            {selectedDiscussionIds.length > 0 ? (
              <Button
                variant="destructive"
                onClick={() => setConfirmingDelete(true)}
                disabled={deleteMutation.isPending}
              >
                <T>Delete selected (</T>
                {selectedDiscussionIds.length})
              </Button>
            ) : null}
          </PermissionGate>
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
            <option value="visible">
              <T>Visible</T>
            </option>
            <option value="hidden">
              <T>Hidden</T>
            </option>
            <option value="archived">
              <T>Archived</T>
            </option>
            <option value="removed">
              <T>Removed</T>
            </option>
          </Select>
        </div>
      </div>
      {confirmingDelete ? (
        <ConfirmDialog
          title={
            selectedDiscussionIds.length === 1
              ? "Delete discussion"
              : `Delete ${selectedDiscussionIds.length} discussions`
          }
          description="Selected discussions and all their comments will be permanently deleted. This cannot be undone."
          confirmLabel={
            selectedDiscussionIds.length === 1 ? "Delete discussion" : "Delete discussions"
          }
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() => deleteMutation.mutate(selectedDiscussionIds)}
        />
      ) : null}

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
            <Th>
              <input
                type="checkbox"
                aria-label="Select all discussions"
                checked={allSelected}
                onChange={toggleAllDiscussions}
              />
            </Th>
            <Th>
              <T>Title</T>
            </Th>
            <Th>
              <T>Author</T>
            </Th>
            <Th>
              <T>Comments</T>
            </Th>
            <Th>
              <T>Status</T>
            </Th>
            <Th>
              <T>Last activity</T>
            </Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={6} />
        ) : discussions.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={6} className="px-3 py-8">
                <EmptyState
                  title="No discussions"
                  hint="Threads started from the storefront appear here."
                />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {discussions.map((entry) => (
              <tr key={entry.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <input
                    type="checkbox"
                    aria-label={`Select ${entry.title}`}
                    checked={selectedDiscussionIds.includes(entry.id)}
                    onChange={() => toggleDiscussion(entry.id)}
                  />
                </Td>
                <Td>
                  <Link
                    to={`/community/${entry.id}`}
                    className="font-medium text-brand hover:underline"
                  >
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
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update."),
  });

  const indexingMutation = useMutation({
    mutationFn: (indexingPolicy: "index" | "noindex") =>
      api.moderateDiscussion(id, undefined, undefined, indexingPolicy),
    onSuccess: async () => {
      await invalidate();
      toast.success("Search indexing updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteDiscussion(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Discussion deleted.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete."),
  });

  const moderateCommentMutation = useMutation({
    mutationFn: (input: { commentId: string; action: string }) =>
      api.moderateComment(input.commentId, input.action),
    onSuccess: async () => {
      await invalidate();
      toast.success("Comment updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update."),
  });

  const deleteCommentMutation = useMutation({
    mutationFn: (commentId: string) => api.deleteComment(commentId),
    onSuccess: async () => {
      await invalidate();
      toast.success("Comment deleted.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete."),
  });

  if (isLoading)
    return (
      <p className="text-sm text-ink-muted">
        <T>Loading discussion…</T>
      </p>
    );
  if (isError || !entry) return <EmptyState title="Discussion not found" />;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">{entry.title}</h1>
          <p className="text-sm text-ink-muted">
            {entry.authorName} ({entry.authorEmail}
            <T>) · started</T> {formatDateTime(entry.createdAt)}
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
              <p className="text-ink-muted">
                <T>Moderation reason</T>
              </p>
              <p className="mt-1 text-sm text-ink">{entry.moderationReason}</p>
            </div>
          ) : null}

          <div>
            <h2 className="mb-2 font-display text-lg text-ink">
              <T>Comments (</T>
              {entry.comments.length})
            </h2>
            {entry.comments.length === 0 ? (
              <p className="text-sm text-ink-muted">
                <T>No comments yet.</T>
              </p>
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
                      <p className="mt-1 text-xs text-ink-muted">
                        <T>Reason:</T> {comment.moderationReason}
                      </p>
                    ) : null}
                    <PermissionGate permission="discussions.moderate">
                      <div className="mt-3 flex flex-wrap gap-2">
                        {comment.status !== "visible" ? (
                          <Button
                            variant="secondary"
                            className="min-h-8 px-2.5 text-xs"
                            onClick={() =>
                              moderateCommentMutation.mutate({
                                commentId: comment.id,
                                action: "restore",
                              })
                            }
                            disabled={moderateCommentMutation.isPending}
                          >
                            <T>Restore</T>
                          </Button>
                        ) : (
                          <Button
                            variant="secondary"
                            className="min-h-8 px-2.5 text-xs"
                            onClick={() =>
                              moderateCommentMutation.mutate({
                                commentId: comment.id,
                                action: "hide",
                              })
                            }
                            disabled={moderateCommentMutation.isPending}
                          >
                            <T>Hide</T>
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
                          <T>Delete</T>
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
            <h2 className="font-display text-base text-ink">
              <T>Moderate thread</T>
            </h2>
            <Field label="Reason (optional)" htmlFor="moderation-reason">
              <Textarea
                id="moderation-reason"
                rows={2}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </Field>
            <Field label="Search indexing" htmlFor="discussion-indexing-policy">
              <Select
                id="discussion-indexing-policy"
                value={entry.indexingPolicy}
                disabled={indexingMutation.isPending}
                onChange={(event) =>
                  indexingMutation.mutate(event.target.value as "index" | "noindex")
                }
              >
                <option value="index">
                  <T>Index</T>
                </option>
                <option value="noindex">
                  <T>No index</T>
                </option>
              </Select>
            </Field>
            {entry.status === "visible" ? (
              <Button
                className="w-full"
                variant="secondary"
                onClick={() => moderateMutation.mutate("hide")}
                disabled={moderateMutation.isPending}
              >
                <T>Hide</T>
              </Button>
            ) : (
              <Button
                className="w-full"
                variant="secondary"
                onClick={() => moderateMutation.mutate("restore")}
                disabled={moderateMutation.isPending}
              >
                <T>Restore (make visible)</T>
              </Button>
            )}
            <Button
              className="w-full"
              variant="secondary"
              onClick={() => moderateMutation.mutate("archive")}
              disabled={moderateMutation.isPending || entry.status === "archived"}
            >
              <T>Archive</T>
            </Button>
            <Button
              className="w-full"
              variant="destructive"
              onClick={() => moderateMutation.mutate("remove")}
              disabled={moderateMutation.isPending || entry.status === "removed"}
            >
              <T>Remove (soft)</T>
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
              <T>Delete permanently</T>
            </Button>
          </aside>
        </PermissionGate>
      </div>
    </div>
  );
}
