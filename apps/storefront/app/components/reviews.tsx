/** Product reviews and ratings (migration 0005, extended by 0057). Renders
 * approved reviews only -- pending/rejected/removed rows never reach the
 * public API in the first place, so there is nothing to filter here. */

import type { ProductReview } from "@truegrit/contracts";

export function StarRating({ rating }: { rating: number }) {
  return (
    <span aria-label={`${rating} out of 5 stars`} className="text-amber-500">
      {"★".repeat(rating)}
      <span className="text-line" aria-hidden>
        {"★".repeat(Math.max(0, 5 - rating))}
      </span>
    </span>
  );
}

export function RatingSummary({ average, count }: { average: number; count: number }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <StarRating rating={Math.round(average)} />
      <span>
        {average.toFixed(1)} ({count} review{count === 1 ? "" : "s"})
      </span>
    </span>
  );
}

export function ProductReviews({
  reviews,
  average,
  count,
}: {
  reviews: ProductReview[];
  average: number;
  count: number;
}) {
  if (reviews.length === 0) {
    return (
      <p className="text-center text-sm text-ink-muted">
        No reviews yet. Reviews appear here once a verified purchaser writes one from their order.
      </p>
    );
  }
  return (
    <div className="mx-auto max-w-3xl">
      <p className="mb-6 text-center text-sm text-ink-muted">
        <RatingSummary average={average} count={count} />
      </p>
      <ul className="space-y-6">
        {reviews.map((review) => (
          <li key={review.id} className="border-t border-line pt-5 first:border-t-0 first:pt-0">
            <StarRating rating={review.rating} />
            {review.title ? <p className="mt-1.5 font-medium text-ink">{review.title}</p> : null}
            <p className="mt-1.5 text-sm text-ink-muted">{review.body}</p>
            <p className="mt-2 text-xs text-ink-muted">
              <span className="font-medium text-ink">{review.authorName}</span>
              {review.verifiedPurchase ? " · Verified purchase" : ""}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
