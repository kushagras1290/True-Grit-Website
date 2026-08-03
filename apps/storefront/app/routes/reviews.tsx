import { Link } from "react-router";

import type { Route } from "./+types/reviews";
import { Section } from "../components/catalogue";
import { StarRating } from "../components/reviews";
import { PageLinkPagination } from "../components/pagination";
import { catalogueRuntime, loadAllReviews } from "../lib/catalogue.server";
import { seoMeta } from "../lib/seo";

const REVIEWS_PAGE_SIZE = 12;

export async function loader({ context, request }: Route.LoaderArgs) {
  const page = Math.max(1, Number(new URL(request.url).searchParams.get("page")) || 1);
  return {
    page,
    pageSize: REVIEWS_PAGE_SIZE,
    reviews: await loadAllReviews(page, REVIEWS_PAGE_SIZE, catalogueRuntime(context)),
  };
}

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Customer reviews",
    description: "Real ratings and reviews from verified True Grit purchases.",
    canonicalPath: "/reviews",
    indexing: "index",
  });
}

export default function ReviewsPage({ loaderData }: Route.ComponentProps) {
  const { reviews, page, pageSize } = loaderData;

  return (
    <Section eyebrow="From our customers" heading="Customer reviews">
      <p className="mb-8 text-center text-sm text-ink-muted" role="status">
        {reviews.total} review{reviews.total === 1 ? "" : "s"} from verified purchases
      </p>

      {reviews.items.length === 0 ? (
        <p className="text-center text-sm text-ink-muted">
          No reviews yet. Reviews appear here once a verified purchaser writes one from their order.
        </p>
      ) : (
        <ul className="mx-auto grid max-w-4xl gap-6 sm:grid-cols-2">
          {reviews.items.map((review) => (
            <li key={review.id} className="rounded-md border border-line bg-surface p-5">
              <StarRating rating={review.rating} />
              {review.title ? <p className="mt-1.5 font-medium text-ink">{review.title}</p> : null}
              <p className="mt-1.5 line-clamp-4 text-sm text-ink-muted">{review.body}</p>
              <p className="mt-3 text-xs text-ink-muted">
                <span className="font-medium text-ink">{review.authorName}</span>
                {review.verifiedPurchase ? " · Verified purchase" : ""}
              </p>
              <Link
                to={`/product/${review.productSlug}`}
                className="mt-2 inline-block text-sm text-brand hover:underline"
              >
                {review.productName}
              </Link>
            </li>
          ))}
        </ul>
      )}

      <PageLinkPagination page={page} pageSize={pageSize} total={reviews.total} />
    </Section>
  );
}
