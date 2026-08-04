import { formatMoney } from "@truegrit/contracts";
import { Ban, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import type { ProductSummary } from "@truegrit/contracts";

import type { Route } from "./+types/order";
import { Section } from "../components/catalogue";
import { RecommendedProducts } from "../components/recommendations";
import { StarRating } from "../components/reviews";
import {
  commerceLive,
  createReturnRequest,
  createReview,
  getBestsellers,
  getMyOrder,
  listMyOrderReviews,
  listMyReturnRequests,
  type MyReview,
  type OrderDetail,
  type ReturnReasonCode,
  type ReturnRequestSummary,
} from "../lib/commerce";
import { useCustomer } from "../lib/customer-auth";
import { seoMeta } from "../lib/seo";
import { useSiteSettings } from "../lib/site-settings";
import { LocalizedText, useLocalizePlural, useLocalizeText } from "../lib/i18n/localized-text";
import { useDateFormatter } from "../lib/i18n/dates";
import { statusSource } from "../lib/i18n/status-labels";

const REASON_OPTIONS: Array<{ value: ReturnReasonCode; label: string }> = [
  { value: "damaged", label: "Arrived damaged" },
  { value: "wrong_item", label: "Wrong item" },
  { value: "quality_issue", label: "Quality issue" },
  { value: "not_as_described", label: "Not as described" },
  { value: "missing_item", label: "Missing item" },
  { value: "other", label: "Something else" },
];

const RETURN_ELIGIBLE_ORDER_STATUSES = new Set(["confirmed", "processing", "completed"]);

function ReturnRequestSection({ order, reference }: { order: OrderDetail; reference: string }) {
  const formatDate = useDateFormatter();
  const localize = useLocalizeText();
  const [requests, setRequests] = useState<ReturnRequestSummary[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [reasonCode, setReasonCode] = useState<ReturnReasonCode>("damaged");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listMyReturnRequests(reference)
      .then((items) => active && setRequests(items))
      .catch(() => active && setRequests([]));
    return () => {
      active = false;
    };
  }, [reference]);

  if (!RETURN_ELIGIBLE_ORDER_STATUSES.has(order.orderStatus) || requests === null) return null;

  const openRequest = requests.find((entry) => entry.status !== "rejected");

  async function submitReturn() {
    if (description.trim().length < 10) {
      setError("Describe the issue in at least 10 characters.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created = await createReturnRequest(reference, {
        reasonCode,
        description: description.trim(),
      });
      setRequests((current) => [created, ...(current ?? [])]);
      setShowForm(false);
      setDescription("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not submit the return request.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-md border border-line bg-surface p-5">
      <h2 className="font-display text-lg text-ink">
        <LocalizedText>Returns</LocalizedText>
      </h2>
      {openRequest ? (
        <div className="mt-2 text-sm text-ink-muted">
          <p>
            <LocalizedText>Return request status:</LocalizedText>{" "}
            <span className="font-medium text-ink">
              {localize(statusSource("returnRequestStatus", openRequest.status))}
            </span>
          </p>
          <p className="mt-1">
            <LocalizedText>Requested</LocalizedText> {formatDate(openRequest.requestedAt)}
          </p>
        </div>
      ) : showForm ? (
        <div className="mt-3 space-y-3">
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-ink">
              <LocalizedText>Reason</LocalizedText>
            </span>
            <select
              className="min-h-9 w-full rounded-sm border border-line-strong bg-surface px-3 text-sm text-ink"
              value={reasonCode}
              onChange={(event) => setReasonCode(event.target.value as ReturnReasonCode)}
            >
              {REASON_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {localize(option.label)}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium text-ink">
              <LocalizedText>What happened?</LocalizedText>
            </span>
            <textarea
              className="min-h-20 w-full rounded-sm border border-line-strong bg-surface px-3 py-2 text-sm text-ink"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={localize("Include what's wrong and any details that will help support.")}
            />
          </label>
          {error ? <p className="text-sm text-danger">{localize(error)}</p> : null}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={submitReturn}
              disabled={submitting}
              className="min-h-9 rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:opacity-50"
            >
              {submitting ? (
                <LocalizedText>{"Submitting…"}</LocalizedText>
              ) : (
                <LocalizedText>{"Submit request"}</LocalizedText>
              )}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="min-h-9 rounded-sm border border-line-strong px-4 text-sm text-ink hover:bg-subtle/50"
            >
              <LocalizedText>Cancel</LocalizedText>
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="mt-3 min-h-9 rounded-sm border border-line-strong px-4 text-sm text-ink hover:bg-subtle/50"
        >
          <LocalizedText>Request a return</LocalizedText>
        </button>
      )}
    </div>
  );
}

const RATING_OPTIONS = [5, 4, 3, 2, 1] as const;

function ReviewLineForm({
  reference,
  productId,
  onCancel,
  onSubmitted,
}: {
  reference: string;
  productId: string;
  onCancel: () => void;
  onSubmitted: () => Promise<void>;
}) {
  const plural = useLocalizePlural();
  const localize = useLocalizeText();
  const [rating, setRating] = useState(5);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (body.trim().length < 10) {
      setError("Write at least 10 characters.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await createReview(reference, {
        productId,
        rating,
        title: title.trim() || undefined,
        body: body.trim(),
      });
      await onSubmitted();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not submit the review.");
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-3 space-y-3">
      <label className="block text-sm">
        <span className="mb-1 block font-medium text-ink">
          <LocalizedText>Rating</LocalizedText>
        </span>
        <select
          className="min-h-9 rounded-sm border border-line-strong bg-surface px-3 text-sm text-ink"
          value={rating}
          onChange={(event) => setRating(Number(event.target.value))}
        >
          {RATING_OPTIONS.map((value) => (
            <option key={value} value={value}>
              {plural("{count} star", "{count} stars", value)}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        <span className="mb-1 block font-medium text-ink">
          <LocalizedText>Title (optional)</LocalizedText>
        </span>
        <input
          className="min-h-9 w-full rounded-sm border border-line-strong bg-surface px-3 text-sm text-ink"
          value={title}
          maxLength={120}
          onChange={(event) => setTitle(event.target.value)}
        />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block font-medium text-ink">
          <LocalizedText>Your review</LocalizedText>
        </span>
        <textarea
          className="min-h-20 w-full rounded-sm border border-line-strong bg-surface px-3 py-2 text-sm text-ink"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder={localize("What did you think of this product?")}
        />
      </label>
      {error ? <p className="text-sm text-danger">{localize(error)}</p> : null}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={submit}
          disabled={submitting}
          className="min-h-9 rounded-sm bg-brand px-4 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? (
            <LocalizedText>{"Submitting…"}</LocalizedText>
          ) : (
            <LocalizedText>{"Submit review"}</LocalizedText>
          )}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={submitting}
          className="min-h-9 rounded-sm border border-line-strong px-4 text-sm text-ink hover:bg-subtle/50"
        >
          <LocalizedText>Cancel</LocalizedText>
        </button>
      </div>
    </div>
  );
}

const REVIEW_ELIGIBLE_ORDER_STATUSES = new Set(["completed"]);

/** One "write a review" prompt per distinct product in the order -- a
 *  multi-variant purchase of the same product (two sizes of the same mango
 *  box) still gets one review slot, matching the API's one-review-per-product-
 *  per-order rule. */
function ReviewSection({ order, reference }: { order: OrderDetail; reference: string }) {
  const [reviews, setReviews] = useState<MyReview[] | null>(null);
  const [openProductId, setOpenProductId] = useState<string | null>(null);

  function refetch() {
    return listMyOrderReviews(reference).then(setReviews);
  }

  useEffect(() => {
    let active = true;
    listMyOrderReviews(reference)
      .then((items) => active && setReviews(items))
      .catch(() => active && setReviews([]));
    return () => {
      active = false;
    };
  }, [reference]);

  if (!REVIEW_ELIGIBLE_ORDER_STATUSES.has(order.orderStatus) || reviews === null) return null;

  const reviewableLines = order.items.filter(
    (item, index, all) =>
      item.productId !== null &&
      all.findIndex((entry) => entry.productId === item.productId) === index,
  );
  if (reviewableLines.length === 0) return null;

  return (
    <div className="rounded-md border border-line bg-surface p-5">
      <h2 className="font-display text-lg text-ink">
        <LocalizedText>Reviews</LocalizedText>
      </h2>
      <ul>
        {reviewableLines.map((item) => {
          const existing = reviews.find((entry) => entry.productId === item.productId);
          return (
            <li
              key={item.productId}
              className="border-t border-line pt-4 first:border-t-0 first:pt-3"
            >
              <p className="text-sm font-medium text-ink">{item.productName}</p>
              {existing ? (
                <div className="mt-1.5 flex items-center gap-2 text-sm">
                  <StarRating rating={existing.rating} />
                  <span className="text-ink-muted">
                    {existing.status === "pending" ? (
                      <LocalizedText>{"Awaiting moderation"}</LocalizedText>
                    ) : existing.status === "approved" ? (
                      <LocalizedText>{"Published"}</LocalizedText>
                    ) : (
                      existing.status
                    )}
                  </span>
                </div>
              ) : openProductId === item.productId ? (
                <ReviewLineForm
                  reference={reference}
                  productId={item.productId!}
                  onCancel={() => setOpenProductId(null)}
                  onSubmitted={async () => {
                    await refetch();
                    setOpenProductId(null);
                  }}
                />
              ) : (
                <button
                  type="button"
                  onClick={() => setOpenProductId(item.productId)}
                  className="mt-1.5 min-h-8 rounded-sm border border-line-strong px-3 text-sm text-ink hover:bg-subtle/50"
                >
                  <LocalizedText>Write a review</LocalizedText>
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function meta({ matches }: Route.MetaArgs) {
  return seoMeta(
    {
      title: "Track your order",
      description: "Order details and delivery progress.",
      canonicalPath: "/account",
      indexing: "noindex",
    },
    matches,
  );
}

type State =
  { kind: "loading" } | { kind: "error"; message: string } | { kind: "loaded"; order: OrderDetail };

const TRACK_STEPS = [
  { label: "Order placed", description: "We've received your order." },
  { label: "Confirmed", description: "Payment settled and order accepted." },
  { label: "Processing", description: "Being picked and packed at the farm hub." },
  { label: "Out for delivery", description: "On its way to your address." },
  { label: "Delivered", description: "Enjoy your order." },
] as const;

/** Map the order's statuses to the furthest reached tracking step (0-4), or -1
 *  when the order was cancelled. */
function currentStep(order: OrderDetail): number {
  if (order.orderStatus === "cancelled") return -1;
  if (order.orderStatus === "completed" || order.fulfilmentStatus === "fulfilled") return 4;
  if (order.fulfilmentStatus === "shipped" || order.fulfilmentStatus === "out_for_delivery")
    return 3;
  if (order.orderStatus === "processing" || order.fulfilmentStatus === "processing") return 2;
  if (order.orderStatus === "confirmed") return 1;
  return 0;
}

function TrackingTimeline({ order }: { order: OrderDetail }) {
  const step = currentStep(order);

  if (step === -1) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-ink">
        <Ban size={18} className="text-danger" aria-hidden />
        <span>
          <LocalizedText>This order was cancelled.</LocalizedText>
        </span>
      </div>
    );
  }

  return (
    <ol className="rounded-md border border-line bg-surface p-5">
      {TRACK_STEPS.map((item, index) => {
        const done = index < step;
        const current = index === step;
        return (
          <li key={item.label} className="flex gap-3 pb-5 last:pb-0">
            <div className="flex flex-col items-center">
              {done ? (
                <CheckCircle2 size={20} className="text-brand" aria-hidden />
              ) : current ? (
                <Loader2 size={20} className="animate-spin text-brand" aria-hidden />
              ) : (
                <Circle size={20} className="text-line" aria-hidden />
              )}
              {index < TRACK_STEPS.length - 1 ? (
                <span
                  className={`mt-1 w-px flex-1 ${index < step ? "bg-brand" : "bg-line"}`}
                  aria-hidden
                />
              ) : null}
            </div>
            <div className="pb-1">
              <p
                className={`text-sm font-medium ${done || current ? "text-ink" : "text-ink-muted"}`}
              >
                {item.label}
                {current ? (
                  <span className="ml-2 rounded-full bg-subtle px-2 py-0.5 text-[11px] text-brand">
                    <LocalizedText>In progress</LocalizedText>
                  </span>
                ) : null}
              </p>
              <p className="text-xs text-ink-muted">{item.description}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export default function OrderPage(_props: Route.ComponentProps) {
  const localize = useLocalizeText();
  const { reference = "" } = useParams();
  const { status } = useCustomer();
  const { recommendations } = useSiteSettings();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [recommended, setRecommended] = useState<ProductSummary[]>([]);

  useEffect(() => {
    if (status !== "authenticated") return;
    let active = true;
    getMyOrder(reference)
      .then((order) => active && setState({ kind: "loaded", order }))
      .catch(() =>
        active ? setState({ kind: "error", message: "We couldn't find that order." }) : null,
      );
    return () => {
      active = false;
    };
  }, [reference, status]);

  // "You might also like" once the order is confirmed -- a standard
  // post-purchase prompt, excluding whatever this order already bought.
  const orderSlugsKey =
    state.kind === "loaded"
      ? state.order.items
          .map((item) => item.productSlug)
          .filter((slug): slug is string => slug !== null)
          .join(",")
      : "";
  useEffect(() => {
    if (state.kind !== "loaded" || !commerceLive || !recommendations.enabled) return;
    let active = true;
    getBestsellers({ excludeSlugs: orderSlugsKey ? orderSlugsKey.split(",") : undefined })
      .then((items) => {
        if (active) setRecommended(items);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.kind, orderSlugsKey, recommendations.enabled]);

  if (status === "anonymous") {
    return (
      <Section eyebrow="Order" heading="Sign in to view this order">
        <Link to="/" className="text-sm text-brand underline-offset-4 hover:underline">
          <LocalizedText>Back home</LocalizedText>
        </Link>
      </Section>
    );
  }

  if (state.kind === "loading") {
    return (
      <Section eyebrow="Order" heading="Loading your order…">
        <p className="text-sm text-ink-muted">
          <LocalizedText>One moment.</LocalizedText>
        </p>
      </Section>
    );
  }

  if (state.kind === "error") {
    return (
      <Section eyebrow="Order" heading="Order not found">
        <p className="text-sm text-ink-muted">{localize(state.message)}</p>
        <Link
          to="/account"
          className="mt-4 inline-flex text-sm text-brand underline-offset-4 hover:underline"
        >
          <LocalizedText>Your account</LocalizedText>
        </Link>
      </Section>
    );
  }

  const { order } = state;
  const paid = order.paymentStatus === "paid";

  return (
    <>
      <Section eyebrow="Track your order" heading={order.reference}>
        <div className="mb-6 flex flex-wrap items-center gap-2 rounded-sm border border-brand/30 bg-subtle/40 px-4 py-3 text-sm text-ink">
          <CheckCircle2 size={18} className="text-brand" aria-hidden />
          <span>
            <LocalizedText>Status:</LocalizedText>{" "}
            {localize(statusSource("orderStatus", order.orderStatus))}
          </span>
          <span className="text-ink-muted">·</span>
          <span>
            <LocalizedText>Payment:</LocalizedText>{" "}
            {localize(statusSource("paymentStatus", order.paymentStatus))}
          </span>
        </div>

        <Link
          to={`/account/orders/${reference}/receipt`}
          className="mb-6 inline-flex min-h-9 items-center rounded-sm border border-line-strong px-3.5 text-sm font-medium text-ink hover:bg-canvas"
        >
          <LocalizedText>View e-receipt</LocalizedText>
        </Link>

        <div className="grid gap-8 lg:grid-cols-[2fr_1fr]">
          <div className="space-y-6">
            <TrackingTimeline order={order} />

            <ReturnRequestSection order={order} reference={reference} />

            <ReviewSection order={order} reference={reference} />

            <div className="overflow-x-auto rounded-md border border-line bg-surface">
              <table className="w-full min-w-[420px] text-left text-sm">
                <thead className="bg-canvas text-xs text-ink-muted uppercase">
                  <tr>
                    <th className="px-4 py-2.5">
                      <LocalizedText>Item</LocalizedText>
                    </th>
                    <th className="px-4 py-2.5">
                      <LocalizedText>Qty</LocalizedText>
                    </th>
                    <th className="px-4 py-2.5">
                      <LocalizedText>Total</LocalizedText>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {order.items.map((item) => (
                    <tr key={item.id} className="border-t border-line">
                      <td className="px-4 py-3">
                        <span className="block font-medium text-ink">{item.productName}</span>
                        <span className="text-xs text-ink-muted">{item.variantName}</span>
                      </td>
                      <td className="px-4 py-3">{item.quantity}</td>
                      <td className="px-4 py-3">
                        {formatMoney(item.lineTotalMinor, order.currencyCode)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <aside className="h-fit rounded-md border border-line bg-surface p-5 shadow-card">
            <h2 className="font-display text-lg text-ink">
              <LocalizedText>Summary</LocalizedText>
            </h2>
            <dl className="mt-3 space-y-1.5 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-muted">
                  <LocalizedText>Subtotal</LocalizedText>
                </dt>
                <dd>{formatMoney(order.subtotalMinor, order.currencyCode)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">
                  <LocalizedText>Delivery</LocalizedText>
                </dt>
                <dd>
                  {order.deliveryMinor === 0 ? (
                    <LocalizedText>{"Free"}</LocalizedText>
                  ) : (
                    formatMoney(order.deliveryMinor, order.currencyCode)
                  )}
                </dd>
              </div>
              <div className="flex justify-between border-t border-line pt-1.5 font-medium">
                <dt>
                  <LocalizedText>Total</LocalizedText>
                </dt>
                <dd>{formatMoney(order.totalMinor, order.currencyCode)}</dd>
              </div>
            </dl>
            <Link
              to="/account"
              className="mt-5 inline-flex text-sm text-brand underline-offset-4 hover:underline"
            >
              <LocalizedText>All your orders</LocalizedText>
            </Link>
          </aside>
        </div>
      </Section>

      <RecommendedProducts
        eyebrow="Complete your order"
        heading="You might also like"
        products={recommended}
      />
    </>
  );
}
