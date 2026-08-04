/** Product reviews and ratings (migration 0005, extended by 0057). Renders
 * approved reviews only -- pending/rejected/removed rows never reach the
 * public API in the first place, so there is nothing to filter here. */

import type { ProductReview } from "@truegrit/contracts";
import { LocalizedText, useLocalizeFormat, useLocalizePlural } from "../lib/i18n/localized-text";

export function StarRating({ rating }: { rating: number }) {
  const format = useLocalizeFormat();
  return (
    <span aria-label={format("{rating} out of 5 stars", { rating })} className="text-amber-500">
      {"★".repeat(rating)}
      <span className="text-line" aria-hidden>
        {"★".repeat(Math.max(0, 5 - rating))}
      </span>
    </span>
  );
}

export function RatingSummary({ average, count }: { average: number; count: number }) {
  const plural = useLocalizePlural();
  return (
    <span className="inline-flex items-center gap-1.5">
      <StarRating rating={Math.round(average)} />
      <span>
        {average.toFixed(1)} ({plural("{count} review", "{count} reviews", count)})
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
        <LocalizedText>
          No reviews yet. Reviews appear here once a verified purchaser writes one from their order.
        </LocalizedText>
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
              {review.verifiedPurchase ? (
                <LocalizedText>{" · Verified purchase"}</LocalizedText>
              ) : (
                ""
              )}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
