/** Product reviews and ratings (migration 0005, extended by 0057).
 *
 * Policed with its own `reviews.view` / `reviews.moderate` pair rather than
 * reusing `discussions.*` -- reviews are commerce-adjacent (tied to orders and
 * products), so Order Manager / Product Manager territory, not the
 * content-moderation roles.
 *
 * A review starts `pending` and is invisible to customers until approved --
 * the opposite posture from discussions/comments, which moderate content that
 * is already live. Approve, reject and remove are all reversible (the row and
 * its history stay); Delete is the one permanent action. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import {
  Button,
  DataTableShell,
  EmptyState,
  Field,
  Input,
  LoadingRows,
  Modal,
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
import { usePermissions } from "../lib/permissions";

function Stars({ rating }: { rating: number }) {
  return (
    <span aria-label={`${rating} out of 5 stars`} className="tracking-tight text-amber-500">
      {"★".repeat(rating)}
      <span className="text-line">{"★".repeat(Math.max(0, 5 - rating))}</span>
    </span>
  );
}

interface EditableReview {
  id: string;
  rating: number;
  title: string | null;
  body: string;
}

/** Staff correction of what a review actually says -- a typo, a stray phone
 *  number, that kind of thing. Distinct from Approve/Reject/Remove above,
 *  which only ever change whether the (unedited) review is shown. */
function EditReviewModal({
  review,
  onClose,
  onSaved,
}: {
  review: EditableReview;
  onClose: () => void;
  onSaved: (input: { rating: number; title: string | null; body: string }) => void;
}) {
  const toast = useToast();
  const [rating, setRating] = useState(review.rating);
  const [title, setTitle] = useState(review.title ?? "");
  const [body, setBody] = useState(review.body);

  const mutation = useMutation({
    mutationFn: () =>
      api.editReview(review.id, { rating, title: title.trim() || null, body: body.trim() }),
    onSuccess: () => {
      onSaved({ rating, title: title.trim() || null, body: body.trim() });
      toast.success("Review updated.");
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the review."),
  });

  return (
    <Modal title="Edit review" onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (body.trim().length < 10) {
            toast.error("Review text must be at least 10 characters.");
            return;
          }
          mutation.mutate();
        }}
      >
        <Field label="Rating" htmlFor="edit-review-rating">
          <Select
            id="edit-review-rating"
            value={rating}
            onChange={(event) => setRating(Number(event.target.value))}
          >
            {[5, 4, 3, 2, 1].map((value) => (
              <option key={value} value={value}>
                {value} star{value === 1 ? "" : "s"}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Title" htmlFor="edit-review-title">
          <Input
            id="edit-review-title"
            value={title}
            maxLength={120}
            onChange={(event) => setTitle(event.target.value)}
          />
        </Field>
        <Field label="Review text" htmlFor="edit-review-body">
          <Textarea
            id="edit-review-body"
            rows={5}
            value={body}
            maxLength={4000}
            onChange={(event) => setBody(event.target.value)}
          />
        </Field>
        <div className="flex justify-end gap-2 border-t border-line pt-3">
          <Button type="button" variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function ReviewsListPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const canModerate = permissions.has("reviews.moderate");
  const [statusFilter, setStatusFilter] = useState("");
  const [ratingFilter, setRatingFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [editingId, setEditingId] = useState<string | null>(null);
  const limit = 25;
  const offset = (page - 1) * limit;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-reviews", statusFilter, ratingFilter, searchQuery, page],
    queryFn: () =>
      api.reviews({
        status: statusFilter || undefined,
        rating: ratingFilter ? Number(ratingFilter) : undefined,
        search: searchQuery || undefined,
        limit,
        offset,
      }),
  });
  const reviews = data?.items ?? [];

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["admin-reviews"] });
  }

  const moderateMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) => {
      const reason =
        action === "reject" || action === "remove"
          ? (prompt("Reason (shown only to staff, optional):") ?? undefined)
          : undefined;
      return api.moderateReview(id, action, reason || undefined);
    },
    onSuccess: async () => {
      await invalidate();
      toast.success("Review updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteReview(id),
    onSuccess: async () => {
      await invalidate();
      toast.success("Review deleted.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete."),
  });

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">Reviews</h1>
          <p className="text-sm text-ink-muted">
            Customer ratings and reviews from verified purchases.
            {data && data.pending > 0 ? (
              <span className="ml-1 text-ink">
                {data.pending} awaiting moderation.
              </span>
            ) : null}
          </p>
        </div>
        <div className="flex gap-2">
          <Select
            value={ratingFilter}
            onChange={(event) => {
              setRatingFilter(event.target.value);
              setPage(1);
            }}
            aria-label="Filter by rating"
          >
            <option value="">All ratings</option>
            <option value="5">5 stars</option>
            <option value="4">4 stars</option>
            <option value="3">3 stars</option>
            <option value="2">2 stars</option>
            <option value="1">1 star</option>
          </Select>
          <Select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setPage(1);
            }}
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
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
          placeholder="Search by review text or author name..."
          aria-label="Search reviews"
        />
      </div>

      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Review</Th>
            <Th>Product</Th>
            <Th>Rating</Th>
            <Th>Author</Th>
            <Th>Status</Th>
            <Th>Posted</Th>
            {canModerate ? <Th>Actions</Th> : null}
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={canModerate ? 7 : 6} />
        ) : reviews.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={canModerate ? 7 : 6} className="px-3 py-8">
                <EmptyState
                  title="No reviews"
                  hint="Reviews customers write from a completed order appear here."
                />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {reviews.map((entry) => (
              <tr key={entry.id} className="border-t border-line hover:bg-canvas/60">
                <Td className="max-w-sm">
                  {entry.title ? <p className="font-medium text-ink">{entry.title}</p> : null}
                  <p className="line-clamp-2 text-ink-muted">{entry.body}</p>
                  {entry.moderationReason ? (
                    <p className="mt-1 text-xs text-ink-muted">Reason: {entry.moderationReason}</p>
                  ) : null}
                </Td>
                <Td>
                  <Link
                    to={`/product/${entry.productSlug}`}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-brand hover:underline"
                  >
                    {entry.productName}
                  </Link>
                </Td>
                <Td>
                  <Stars rating={entry.rating} />
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
                      <Button variant="secondary" onClick={() => setEditingId(entry.id)}>
                        Edit
                      </Button>
                      {entry.status !== "approved" ? (
                        <Button
                          variant="secondary"
                          onClick={() =>
                            moderateMutation.mutate({ id: entry.id, action: "approve" })
                          }
                          disabled={moderateMutation.isPending}
                        >
                          Approve
                        </Button>
                      ) : null}
                      {entry.status !== "rejected" ? (
                        <Button
                          variant="secondary"
                          onClick={() =>
                            moderateMutation.mutate({ id: entry.id, action: "reject" })
                          }
                          disabled={moderateMutation.isPending}
                        >
                          Reject
                        </Button>
                      ) : null}
                      {entry.status !== "removed" ? (
                        <Button
                          variant="secondary"
                          onClick={() =>
                            moderateMutation.mutate({ id: entry.id, action: "remove" })
                          }
                          disabled={moderateMutation.isPending}
                        >
                          Remove
                        </Button>
                      ) : null}
                      <Button
                        variant="destructive"
                        onClick={() => {
                          if (confirm("Permanently delete this review? This cannot be undone.")) {
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
      <Pagination page={page} onPageChange={setPage} rowCount={reviews.length} limit={limit} />

      {editingId
        ? (() => {
            const editing = reviews.find((entry) => entry.id === editingId);
            if (!editing) return null;
            return (
              <EditReviewModal
                review={editing}
                onClose={() => setEditingId(null)}
                onSaved={() => {
                  void invalidate();
                }}
              />
            );
          })()
        : null}
    </div>
  );
}
