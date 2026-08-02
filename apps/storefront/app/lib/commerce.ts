/**
 * Storefront commerce client: checkout and customer order history.
 *
 * Talks to the customer-facing API with cookies. Requires `VITE_API_URL`; in
 * demo-data mode there is no server to place an order against, so the calls
 * surface a clear error and the checkout UI explains that a live API is needed.
 */

import type {
  CustomerAddress,
  ProductSummary,
  SubscriptionFrequency,
  SubscriptionRow,
} from "@truegrit/contracts";

import { AuthError } from "./customer-auth";
import { getPublicApiUrl, hasPublicApiUrl } from "./public-env";

export const commerceLive = hasPublicApiUrl();

export interface CheckoutItem {
  variantId: string;
  quantity: number;
}

export interface DeliveryAddress {
  recipientName: string;
  phoneE164?: string;
  line1: string;
  line2?: string;
  city: string;
  state: string;
  postalCode: string;
  countryCode?: string;
}

export interface OrderPayment {
  method: string;
  razorpayKeyId?: string;
  razorpayOrderId?: string;
  paypalClientId?: string;
  paypalOrderId?: string;
  /** For PayPal this is the *converted* charge (e.g. USD cents), not the INR
   *  order total — PayPal cannot settle INR to an Indian merchant. */
  amountMinor?: number;
  currency?: string;
}

export interface PlacedOrder {
  id: string;
  reference: string;
  currencyCode: string;
  subtotalMinor: number;
  discountMinor: number;
  deliveryMinor: number;
  totalMinor: number;
  orderStatus: string;
  paymentStatus: string;
  couponCode: string | null;
  payment?: OrderPayment;
}

export interface PaymentMethodsInfo {
  methods: string[];
  currency: string;
  codMaxMinor: number;
  razorpayKeyId: string;
  paypalClientId: string;
  /** What an overseas buyer is charged in. Never INR. */
  paypalCurrency: string;
}

export interface OrderSummary {
  reference: string;
  currencyCode: string;
  totalMinor: number;
  orderStatus: string;
  paymentStatus: string;
  fulfilmentStatus: string;
  placedAt: string;
  itemCount: number;
}

export interface OrderLine {
  id: string;
  /** Null only when the product was later deleted -- there is nothing left to
   *  review, so the storefront hides the "write a review" action for that
   *  line rather than posting a review against a product id that no longer
   *  exists. */
  productId: string | null;
  productSlug: string | null;
  productName: string;
  variantName: string;
  sku: string;
  quantity: number;
  unitMinor: number;
  lineTotalMinor: number;
}

export interface OrderDetail {
  reference: string;
  currencyCode: string;
  subtotalMinor: number;
  deliveryMinor: number;
  discountMinor: number;
  taxMinor: number;
  totalMinor: number;
  orderStatus: string;
  paymentStatus: string;
  fulfilmentStatus: string;
  placedAt: string;
  deliveryAddress: DeliveryAddress | null;
  items: OrderLine[];
}

export interface ContactMessage {
  name: string;
  email: string;
  /** Required. Normalised to E.164 by the API, which rejects anything it
   *  cannot ring — see `domain/phone.py`. */
  phone: string;
  subject: string;
  message: string;
}

interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = getPublicApiUrl();
  if (!apiUrl) {
    throw new AuthError("Checkout needs the live API (set VITE_API_URL).", 503, "demo_mode");
  }
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: init?.body
      ? { "content-type": "application/json", ...(init?.headers ?? {}) }
      : init?.headers,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null;
    throw new AuthError(
      body?.error?.message ?? `Request failed (${response.status})`,
      response.status,
      body?.error?.code ?? "request_failed",
    );
  }
  return (await response.json()) as T;
}

export function getPaymentMethods(): Promise<PaymentMethodsInfo> {
  return request<PaymentMethodsInfo>("/v1/public/payment-methods");
}

export interface DeliverySettingsInfo {
  feeMinor: number;
  freeThresholdMinor: number;
}

export function getDeliverySettings(): Promise<DeliverySettingsInfo> {
  return request<DeliverySettingsInfo>("/v1/public/delivery-settings");
}

export interface FeaturedPromotionInfo {
  id: string;
  name: string;
  headline: string;
  description: string | null;
  code: string | null;
}

/** The current best active promotion, resolved the same way the homepage
 *  banner's "rule" mode does -- checkout has no block config of its own to
 *  read a manual pin from, so it always shows whichever promotion currently
 *  has priority, same as the default homepage banner setup. Resolves to
 *  `null` (not an error) when the sitewide switch is off or nothing
 *  currently qualifies. */
export function getFeaturedPromotion(): Promise<FeaturedPromotionInfo | null> {
  return request<{ promotion: FeaturedPromotionInfo | null }>(
    "/v1/public/promotions/featured",
  ).then((body) => body.promotion);
}

/** Real bestsellers -- ranked by quantity actually sold, not a curated list.
 *  Client-side (not the server loader `loadBestsellers` in
 *  `catalogue.server.ts`) because the basket page needs to exclude whatever
 *  is already in the basket, and the basket itself only exists client-side
 *  (localStorage). Empty (not an error) while the sitewide switch is off. */
export function getBestsellers(options: {
  limit?: number;
  excludeSlugs?: string[];
}): Promise<ProductSummary[]> {
  const params = new URLSearchParams({ limit: String(options.limit ?? 8) });
  if (options.excludeSlugs && options.excludeSlugs.length > 0) {
    params.set("exclude", options.excludeSlugs.join(","));
  }
  return request<{ items: ProductSummary[] }>(
    `/v1/public/recommendations/bestsellers?${params.toString()}`,
  ).then((body) => body.items);
}

export interface DiscountPreview {
  code: string | null;
  headline: string;
  discountMinor: number;
  freeDelivery: boolean;
  deliveryMinor: number;
}

/** Validates a coupon code against the current basket and returns the real
 *  discount it would apply -- no order is placed and no redemption is
 *  recorded. Rejects (via `AuthError`) with the same message `placeOrder`
 *  would show if the code were submitted as-is, so the compact checkout box
 *  can surface it before the customer commits. */
export function previewDiscount(
  couponCode: string,
  subtotalMinor: number,
): Promise<DiscountPreview> {
  return request<DiscountPreview>("/v1/public/checkout/preview-discount", {
    method: "POST",
    body: JSON.stringify({ couponCode, subtotalMinor }),
  });
}

export function placeOrder(
  items: CheckoutItem[],
  deliveryAddress: DeliveryAddress,
  paymentMethod: string = "cod",
  idempotencyKey?: string,
  couponCode?: string,
): Promise<PlacedOrder> {
  return request<PlacedOrder>("/v1/public/checkout", {
    method: "POST",
    body: JSON.stringify({ items, deliveryAddress, paymentMethod, idempotencyKey, couponCode }),
  });
}

/** One key per checkout attempt-group: minted when the checkout page loads
 *  and reused across every retry of that same submission (a double-click, a
 *  timeout-and-resend), so a retried request returns the order it already
 *  placed instead of a second one. A fresh page load mints a new key, which
 *  is correct — that is a new attempt, not a retry of the old one. */
export function newCheckoutIdempotencyKey(): string {
  return createPaymentWindowToken();
}

interface RazorpayResult {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

export interface RazorpayPrefill {
  name: string;
  email?: string;
  contact?: string;
}

export interface RazorpayWindowPayload {
  order: PlacedOrder;
  prefill: RazorpayPrefill;
}

const RAZORPAY_WINDOW_STORAGE_PREFIX = "truegrit:razorpay:";

/** Correlates a payment popup with the tab that opened it. Shared by every
 *  gateway — it identifies a window, not a provider. */
function createPaymentWindowToken(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function razorpayWindowStorageKey(token: string): string {
  return `${RAZORPAY_WINDOW_STORAGE_PREFIX}${token}`;
}

export function readRazorpayWindowPayload(token: string): RazorpayWindowPayload | null {
  if (typeof window === "undefined") return null;
  const key = razorpayWindowStorageKey(token);
  const raw = window.localStorage.getItem(key);
  window.localStorage.removeItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as RazorpayWindowPayload;
  } catch {
    return null;
  }
}

function isRazorpayWindowMessage(data: unknown): data is {
  source: "truegrit:razorpay";
  token: string;
  status: "paid" | "failed" | "cancelled";
  order?: PlacedOrder & { ok: boolean };
  message?: string;
} {
  return (
    typeof data === "object" &&
    data !== null &&
    (data as { source?: unknown }).source === "truegrit:razorpay" &&
    typeof (data as { token?: unknown }).token === "string" &&
    ["paid", "failed", "cancelled"].includes(String((data as { status?: unknown }).status))
  );
}

export function verifyRazorpayPayment(
  orderId: string,
  result: RazorpayResult,
): Promise<PlacedOrder & { ok: boolean }> {
  return request<PlacedOrder & { ok: boolean }>("/v1/public/payments/razorpay/verify", {
    method: "POST",
    body: JSON.stringify({
      orderId,
      razorpayOrderId: result.razorpay_order_id,
      razorpayPaymentId: result.razorpay_payment_id,
      razorpaySignature: result.razorpay_signature,
    }),
  });
}

const RAZORPAY_SCRIPT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

function loadRazorpayScript(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("Razorpay needs a browser."));
  const w = window as unknown as { Razorpay?: unknown };
  if (w.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = RAZORPAY_SCRIPT_SRC;
    script.onload = () => resolve();
    script.onerror = () =>
      reject(new AuthError("Could not load the payment widget.", 502, "payment_error"));
    document.head.appendChild(script);
  });
}

/** Open Razorpay checkout for a pending order and resolve once the payment is
 *  verified server-side. Rejects if the customer dismisses the widget. */
export async function payWithRazorpay(
  order: PlacedOrder,
  // `email` and `contact` are both optional because an account may legitimately
  // have only one of them: phone-only signups have no address, and Google
  // sign-ups arrive with no number. Razorpay simply leaves a blank field for the
  // customer to fill, so passing undefined is better than passing "".
  prefill: RazorpayPrefill,
): Promise<PlacedOrder & { ok: boolean }> {
  const payment = order.payment;
  if (!payment?.razorpayOrderId || !payment.razorpayKeyId) {
    throw new AuthError("The payment could not be started.", 500, "payment_error");
  }
  await loadRazorpayScript();
  const Razorpay = (
    window as unknown as { Razorpay: new (options: unknown) => { open: () => void } }
  ).Razorpay;
  return new Promise((resolve, reject) => {
    const checkout = new Razorpay({
      key: payment.razorpayKeyId,
      order_id: payment.razorpayOrderId,
      amount: payment.amountMinor,
      currency: payment.currency,
      name: "True Grit",
      description: `Order ${order.reference}`,
      prefill,
      theme: { color: "#1f3d2b" },
      handler: (result: RazorpayResult) => {
        verifyRazorpayPayment(order.id, result).then(resolve).catch(reject);
      },
      modal: {
        ondismiss: () =>
          reject(new AuthError("Payment was cancelled before it completed.", 499, "cancelled")),
      },
    });
    checkout.open();
  });
}

export function openRazorpayPaymentWindow(): Window | null {
  if (typeof window === "undefined") return null;
  const width = 520;
  const height = 760;
  const left = Math.max(0, window.screenX + Math.round((window.outerWidth - width) / 2));
  const top = Math.max(0, window.screenY + Math.round((window.outerHeight - height) / 2));
  return window.open(
    "/payment/razorpay?status=starting",
    "truegrit_razorpay_checkout",
    [
      "popup=yes",
      "resizable=yes",
      "scrollbars=yes",
      `width=${width}`,
      `height=${height}`,
      `left=${left}`,
      `top=${top}`,
    ].join(","),
  );
}

export function payWithRazorpayWindow(
  order: PlacedOrder,
  prefill: RazorpayPrefill,
  paymentWindow: Window | null,
): Promise<PlacedOrder & { ok: boolean }> {
  if (typeof window === "undefined" || !paymentWindow || paymentWindow.closed) {
    return payWithRazorpay(order, prefill);
  }

  const token = createPaymentWindowToken();
  try {
    window.localStorage.setItem(
      razorpayWindowStorageKey(token),
      JSON.stringify({ order, prefill } satisfies RazorpayWindowPayload),
    );
  } catch {
    return payWithRazorpay(order, prefill);
  }

  return new Promise((resolve, reject) => {
    let closedTimer: number | undefined;
    const cleanup = () => {
      window.removeEventListener("message", handleMessage);
      window.localStorage.removeItem(razorpayWindowStorageKey(token));
      if (closedTimer !== undefined) window.clearInterval(closedTimer);
    };
    const fail = (message: string, code = "payment_error") => {
      cleanup();
      reject(new AuthError(message, 499, code));
    };
    const handleMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || !isRazorpayWindowMessage(event.data)) return;
      if (event.data.token !== token) return;
      cleanup();
      if (event.data.status === "paid" && event.data.order) {
        resolve(event.data.order);
        return;
      }
      if (event.data.status === "paid") {
        reject(
          new AuthError(
            "Payment was verified, but the order result was incomplete.",
            502,
            "payment_error",
          ),
        );
        return;
      }
      reject(
        new AuthError(
          event.data.message ?? "Payment was cancelled before it completed.",
          499,
          event.data.status === "cancelled" ? "cancelled" : "payment_error",
        ),
      );
    };

    window.addEventListener("message", handleMessage);
    closedTimer = window.setInterval(() => {
      if (paymentWindow.closed) {
        fail("Payment window was closed before the payment completed.", "cancelled");
      }
    }, 800);
    paymentWindow.location.assign(`/payment/razorpay?token=${encodeURIComponent(token)}`);
    paymentWindow.focus();
  });
}

// --- PayPal (international) --------------------------------------------------

/**
 * PayPal is the cross-border lane: PayPal closed domestic India payments in
 * 2021, so it exists here for someone abroad paying for delivery into India.
 * The buyer is charged a converted foreign-currency amount, never the INR total.
 *
 * The flow differs from Razorpay in one important way: Razorpay hands the
 * browser a signature the API can verify offline, whereas a PayPal approval is
 * not money until the *server* captures it. So `onApprove` below reports to our
 * API and the API does the capturing — nothing the browser says is trusted.
 */

export interface PaypalWindowPayload {
  order: PlacedOrder;
}

const PAYPAL_WINDOW_STORAGE_PREFIX = "truegrit:paypal:";

function paypalWindowStorageKey(token: string): string {
  return `${PAYPAL_WINDOW_STORAGE_PREFIX}${token}`;
}

export function readPaypalWindowPayload(token: string): PaypalWindowPayload | null {
  if (typeof window === "undefined") return null;
  const key = paypalWindowStorageKey(token);
  const raw = window.localStorage.getItem(key);
  window.localStorage.removeItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PaypalWindowPayload;
  } catch {
    return null;
  }
}

function isPaypalWindowMessage(data: unknown): data is {
  source: "truegrit:paypal";
  token: string;
  status: "paid" | "failed" | "cancelled";
  order?: PlacedOrder & { ok: boolean };
  message?: string;
} {
  return (
    typeof data === "object" &&
    data !== null &&
    (data as { source?: unknown }).source === "truegrit:paypal" &&
    typeof (data as { token?: unknown }).token === "string" &&
    ["paid", "failed", "cancelled"].includes(String((data as { status?: unknown }).status))
  );
}

/** Ask the API to capture the approved PayPal order. This — not the browser's
 *  `onApprove` — is what makes the order paid. */
export function capturePaypalPayment(
  orderId: string,
  paypalOrderId: string,
): Promise<PlacedOrder & { ok: boolean }> {
  return request<PlacedOrder & { ok: boolean }>("/v1/public/payments/paypal/capture", {
    method: "POST",
    body: JSON.stringify({ orderId, paypalOrderId }),
  });
}

interface PaypalSdk {
  Buttons: (config: {
    createOrder: () => Promise<string> | string;
    onApprove: (data: { orderID: string }) => Promise<void> | void;
    onCancel: () => void;
    onError: (error: unknown) => void;
    style?: Record<string, unknown>;
  }) => { render: (container: HTMLElement | string) => Promise<void> };
}

let paypalSdkPromise: Promise<PaypalSdk> | null = null;

function loadPaypalSdk(clientId: string, currency: string): Promise<PaypalSdk> {
  if (typeof window === "undefined") {
    return Promise.reject(new AuthError("PayPal needs a browser.", 500, "payment_error"));
  }
  const existing = (window as unknown as { paypal?: PaypalSdk }).paypal;
  if (existing) return Promise.resolve(existing);
  if (paypalSdkPromise) return paypalSdkPromise;

  paypalSdkPromise = new Promise<PaypalSdk>((resolve, reject) => {
    const script = document.createElement("script");
    const params = new URLSearchParams({
      "client-id": clientId,
      currency,
      intent: "capture",
      // No funding sources we cannot settle: this account takes card + PayPal
      // balance only.
      "disable-funding": "credit,paylater",
    });
    script.src = `https://www.paypal.com/sdk/js?${params.toString()}`;
    script.onload = () => {
      const sdk = (window as unknown as { paypal?: PaypalSdk }).paypal;
      if (sdk) {
        resolve(sdk);
        return;
      }
      paypalSdkPromise = null;
      reject(new AuthError("Could not load the PayPal widget.", 502, "payment_error"));
    };
    script.onerror = () => {
      paypalSdkPromise = null;
      reject(new AuthError("Could not load the PayPal widget.", 502, "payment_error"));
    };
    document.head.appendChild(script);
  });
  return paypalSdkPromise;
}

/** Render PayPal's buttons into `container` and resolve once our API has
 *  captured the payment. Rejects if the buyer cancels. */
export async function payWithPaypal(
  order: PlacedOrder,
  container: HTMLElement,
): Promise<PlacedOrder & { ok: boolean }> {
  const payment = order.payment;
  if (!payment?.paypalOrderId || !payment.paypalClientId || !payment.currency) {
    throw new AuthError("The payment could not be started.", 500, "payment_error");
  }
  const sdk = await loadPaypalSdk(payment.paypalClientId, payment.currency);

  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      fn();
    };
    sdk
      .Buttons({
        // The order already exists server-side; the buttons just adopt it. This
        // is what stops the browser choosing its own amount.
        createOrder: () => payment.paypalOrderId as string,
        onApprove: async (data) => {
          try {
            const paid = await capturePaypalPayment(order.id, data.orderID);
            finish(() => resolve(paid));
          } catch (caught) {
            finish(() =>
              reject(
                caught instanceof AuthError
                  ? caught
                  : new AuthError("We could not confirm your payment.", 502, "payment_error"),
              ),
            );
          }
        },
        onCancel: () =>
          finish(() =>
            reject(new AuthError("Payment was cancelled before it completed.", 499, "cancelled")),
          ),
        onError: () =>
          finish(() =>
            reject(new AuthError("PayPal could not complete this payment.", 502, "payment_error")),
          ),
        style: { layout: "vertical", color: "gold", shape: "rect", label: "paypal" },
      })
      .render(container)
      .catch(() =>
        finish(() =>
          reject(new AuthError("Could not show the PayPal buttons.", 502, "payment_error")),
        ),
      );
  });
}

export function openPaypalPaymentWindow(): Window | null {
  if (typeof window === "undefined") return null;
  const width = 520;
  const height = 760;
  const left = Math.max(0, window.screenX + Math.round((window.outerWidth - width) / 2));
  const top = Math.max(0, window.screenY + Math.round((window.outerHeight - height) / 2));
  return window.open(
    "/payment/paypal?status=starting",
    "truegrit_paypal_checkout",
    [
      "popup=yes",
      "resizable=yes",
      "scrollbars=yes",
      `width=${width}`,
      `height=${height}`,
      `left=${left}`,
      `top=${top}`,
    ].join(","),
  );
}

export function payWithPaypalWindow(
  order: PlacedOrder,
  paymentWindow: Window | null,
): Promise<PlacedOrder & { ok: boolean }> {
  if (typeof window === "undefined" || !paymentWindow || paymentWindow.closed) {
    return Promise.reject(
      new AuthError(
        "We couldn't open the PayPal window. Please allow pop-ups and try again.",
        499,
        "payment_error",
      ),
    );
  }

  const token = createPaymentWindowToken();
  try {
    window.localStorage.setItem(
      paypalWindowStorageKey(token),
      JSON.stringify({ order } satisfies PaypalWindowPayload),
    );
  } catch {
    return Promise.reject(
      new AuthError("We couldn't start the PayPal payment.", 500, "payment_error"),
    );
  }

  return new Promise((resolve, reject) => {
    let closedTimer: number | undefined;
    const cleanup = () => {
      window.removeEventListener("message", handleMessage);
      window.localStorage.removeItem(paypalWindowStorageKey(token));
      if (closedTimer !== undefined) window.clearInterval(closedTimer);
    };
    const handleMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || !isPaypalWindowMessage(event.data)) return;
      if (event.data.token !== token) return;
      cleanup();
      if (event.data.status === "paid" && event.data.order) {
        resolve(event.data.order);
        return;
      }
      reject(
        new AuthError(
          event.data.message ?? "Payment was cancelled before it completed.",
          499,
          event.data.status === "cancelled" ? "cancelled" : "payment_error",
        ),
      );
    };

    window.addEventListener("message", handleMessage);
    closedTimer = window.setInterval(() => {
      if (paymentWindow.closed) {
        cleanup();
        reject(
          new AuthError(
            "Payment window was closed before the payment completed.",
            499,
            "cancelled",
          ),
        );
      }
    }, 800);
    paymentWindow.location.assign(`/payment/paypal?token=${encodeURIComponent(token)}`);
    paymentWindow.focus();
  });
}

export function listMyOrders(): Promise<OrderSummary[]> {
  return request<{ items: OrderSummary[] }>("/v1/public/orders").then((body) => body.items);
}

export function getMyOrder(reference: string): Promise<OrderDetail> {
  return request<OrderDetail>(`/v1/public/orders/${encodeURIComponent(reference)}`);
}

export type ReturnReasonCode =
  "damaged" | "wrong_item" | "quality_issue" | "not_as_described" | "missing_item" | "other";

export interface ReturnRequestSummary {
  id: string;
  orderReference: string;
  reasonCode: ReturnReasonCode;
  status: string;
  resolutionType: string | null;
  requestedAt: string;
  resolvedAt: string | null;
}

export function listMyReturnRequests(reference: string): Promise<ReturnRequestSummary[]> {
  return request<{ items: ReturnRequestSummary[] }>(
    `/v1/public/orders/${encodeURIComponent(reference)}/return-requests`,
  ).then((body) => body.items);
}

export function createReturnRequest(
  reference: string,
  input: {
    orderItemId?: string;
    reasonCode: ReturnReasonCode;
    description: string;
    requestedRefundAmountMinor?: number;
  },
): Promise<ReturnRequestSummary> {
  return request<ReturnRequestSummary>(
    `/v1/public/orders/${encodeURIComponent(reference)}/return-requests`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export type ReviewStatus = "pending" | "approved" | "rejected" | "removed";

/** A review the calling customer wrote against one line of this order.
 *  Carries `status` so the order page can say "pending moderation" rather
 *  than implying the review is already live. */
export interface MyReview {
  id: string;
  productId: string;
  productName: string;
  productSlug: string;
  rating: number;
  title: string | null;
  body: string;
  status: ReviewStatus;
  createdAt: string;
}

export function listMyOrderReviews(reference: string): Promise<MyReview[]> {
  return request<{ items: MyReview[] }>(
    `/v1/public/orders/${encodeURIComponent(reference)}/reviews`,
  ).then((body) => body.items);
}

export function createReview(
  reference: string,
  input: { productId: string; rating: number; title?: string; body: string },
): Promise<{ id: string; status: string }> {
  return request<{ id: string; status: string }>(
    `/v1/public/orders/${encodeURIComponent(reference)}/reviews`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

// ---------------------------------------------------------------------------
// Delivery addresses -- reusable, unlike the ad-hoc address ordinary
// checkout takes on `DeliveryAddress` above. Only Subscribe & Save needs one
// (a renewal has no request to take an address from); see
// `services.addresses` on the API for why this table was dormant until now.
// ---------------------------------------------------------------------------

export function listMyAddresses(): Promise<CustomerAddress[]> {
  return request<{ items: CustomerAddress[] }>("/v1/public/addresses").then(
    (body) => body.items,
  );
}

export function createAddress(input: {
  label?: string;
  recipientName: string;
  phoneE164?: string;
  line1: string;
  line2?: string;
  city: string;
  state: string;
  postalCode: string;
  countryCode?: string;
}): Promise<CustomerAddress> {
  return request<CustomerAddress>("/v1/public/addresses", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

// ---------------------------------------------------------------------------
// Subscriptions ("Subscribe & Save") -- recurring cash-on-delivery
// deliveries of a single product variant. Off sitewide unless an owner has
// switched it on (`useSiteSettings().subscriptions.enabled`); the API
// itself also refuses creation while off, so this is UX, not enforcement.
// ---------------------------------------------------------------------------

export function getSubscriptionDiscountPercent(): Promise<number> {
  return request<{ discountPercent: number }>("/v1/public/subscription-settings").then(
    (body) => body.discountPercent,
  );
}

export function listMySubscriptions(): Promise<SubscriptionRow[]> {
  return request<{ items: SubscriptionRow[] }>("/v1/public/subscriptions").then(
    (body) => body.items,
  );
}

export function createSubscription(input: {
  variantId: string;
  quantity: number;
  frequency: SubscriptionFrequency;
  addressId: string;
}): Promise<SubscriptionRow> {
  return request<SubscriptionRow>("/v1/public/subscriptions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function pauseSubscription(subscriptionId: string): Promise<SubscriptionRow> {
  return request<SubscriptionRow>(
    `/v1/public/subscriptions/${encodeURIComponent(subscriptionId)}/pause`,
    { method: "POST" },
  );
}

export function resumeSubscription(subscriptionId: string): Promise<SubscriptionRow> {
  return request<SubscriptionRow>(
    `/v1/public/subscriptions/${encodeURIComponent(subscriptionId)}/resume`,
    { method: "POST" },
  );
}

export function cancelSubscription(subscriptionId: string): Promise<SubscriptionRow> {
  return request<SubscriptionRow>(
    `/v1/public/subscriptions/${encodeURIComponent(subscriptionId)}/cancel`,
    { method: "POST" },
  );
}

export function sendContactMessage(input: ContactMessage): Promise<{ ok: boolean; id: string }> {
  return request<{ ok: boolean; id: string }>("/v1/public/contact", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
