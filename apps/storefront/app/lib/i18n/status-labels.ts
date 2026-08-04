/**
 * Human labels for the enum values the API returns.
 *
 * The storefront used to render these raw — `order.orderStatus` printed
 * `pending_payment` with an underscore swapped for a space and a CSS
 * `capitalize`. That is untranslatable by construction: the value is a database
 * token, not a sentence, so no catalogue lookup could ever match it. Mapping
 * each token to English source text here gives the normal source-text
 * translation path something to translate, and gives every locale one place to
 * cover.
 *
 * An unrecognised token still renders readably. A new status added to the
 * database and not yet listed here degrades to `pending payment` rather than
 * disappearing from the order summary.
 */

const ORDER_STATUS: Readonly<Record<string, string>> = {
  pending_payment: "Pending payment",
  confirmed: "Confirmed",
  processing: "Processing",
  completed: "Completed",
  cancelled: "Cancelled",
};

const PAYMENT_STATUS: Readonly<Record<string, string>> = {
  not_required: "Not required",
  pending: "Pending",
  authorized: "Authorised",
  paid: "Paid",
  partially_refunded: "Partially refunded",
  refunded: "Refunded",
  failed: "Failed",
};

const FULFILMENT_STATUS: Readonly<Record<string, string>> = {
  unfulfilled: "Unfulfilled",
  reserved: "Reserved",
  picking: "Picking",
  packed: "Packed",
  quality_checked: "Quality checked",
  dispatched: "Dispatched",
  partially_fulfilled: "Partially fulfilled",
  fulfilled: "Fulfilled",
  cancelled: "Cancelled",
};

const SUBSCRIPTION_STATUS: Readonly<Record<string, string>> = {
  active: "Active",
  paused: "Paused",
  cancelled: "Cancelled",
};

const RETURN_REQUEST_STATUS: Readonly<Record<string, string>> = {
  requested: "Requested",
  under_review: "Under review",
  approved: "Approved",
  rejected: "Rejected",
  refunded: "Refunded",
  replaced: "Replaced",
  completed: "Completed",
  cancelled: "Cancelled",
};

const SUBMISSION_STATUS: Readonly<Record<string, string>> = {
  submitted: "Submitted",
  under_review: "Under review",
  changes_requested: "Changes requested",
  approved: "Approved",
  rejected: "Not published",
};

const SUBSCRIPTION_FREQUENCY: Readonly<Record<string, string>> = {
  weekly: "Every week",
  biweekly: "Every 2 weeks",
  monthly: "Every month",
};

const SEARCH_GROUP: Readonly<Record<string, string>> = {
  products: "Products",
  farms: "Farms",
  recipes: "Recipes",
  articles: "Blog",
};

const RETURN_REASON: Readonly<Record<string, string>> = {
  damaged: "Arrived damaged",
  wrong_item: "Wrong item",
  quality_issue: "Quality issue",
  not_as_described: "Not as described",
  missing_item: "Missing item",
  other: "Something else",
};

/**
 * Fixed English phrases the API composes and the storefront renders verbatim.
 *
 * These never appear as a literal anywhere in this codebase — they are built in
 * Python (`repositories/catalogue.py`, `repositories/content.py`, the public
 * breadcrumb builder) and arrive as data. Listing them here is what puts them
 * in the extractor's reach, so `localize(step.label)` at the render site has an
 * entry to find. Keep in step with the API; a phrase that drifts simply falls
 * through untranslated rather than breaking.
 */
const API_COMPOSED_PHRASES: Readonly<Record<string, string>> = {
  farm: "Farm",
  certification: "Certification",
  qualityCheck: "Quality check",
  delivery: "Delivery",
  qualityCheckDetail: "Checked at the fulfilment centre before dispatch",
  deliveryDetail: "Shipped with full lot traceability",
  certificationPending: "In review",
  verifiedFarm: "Verified farm",
  home: "Home",
  shop: "Shop",
};

const REGISTRIES = {
  orderStatus: ORDER_STATUS,
  paymentStatus: PAYMENT_STATUS,
  fulfilmentStatus: FULFILMENT_STATUS,
  subscriptionStatus: SUBSCRIPTION_STATUS,
  returnRequestStatus: RETURN_REQUEST_STATUS,
  submissionStatus: SUBMISSION_STATUS,
  subscriptionFrequency: SUBSCRIPTION_FREQUENCY,
  searchGroup: SEARCH_GROUP,
  returnReason: RETURN_REASON,
} as const;

export type StatusKind = keyof typeof REGISTRIES;

/** `pending_payment` -> `Pending payment`, for tokens no registry lists. */
function humanize(token: string): string {
  const spaced = token.replaceAll("_", " ").trim();
  if (spaced.length === 0) return spaced;
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/**
 * The English source text for `token`, ready to hand to `localize()`.
 *
 * Returns source text rather than translated text so callers use the one
 * translation path the rest of the storefront uses, and so this module stays
 * free of React and usable from loaders.
 */
export function statusSource(kind: StatusKind, token: string | null | undefined): string {
  if (!token) return "";
  return REGISTRIES[kind][token] ?? humanize(token);
}

/** Every label this module can produce, for the catalogue extractor. */
export const ALL_STATUS_SOURCES: readonly string[] = [
  ...Object.values(REGISTRIES).flatMap((registry) => Object.values(registry)),
  ...Object.values(API_COMPOSED_PHRASES),
];
