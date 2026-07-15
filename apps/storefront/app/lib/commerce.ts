/**
 * Storefront commerce client: checkout and customer order history.
 *
 * Talks to the customer-facing API with cookies. Requires `VITE_API_URL`; in
 * demo-data mode there is no server to place an order against, so the calls
 * surface a clear error and the checkout UI explains that a live API is needed.
 */

import { AuthError } from "./customer-auth";

const API_URL = import.meta.env.VITE_API_URL as string | undefined;
export const commerceLive = Boolean(API_URL);

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
}

export interface OrderPayment {
  method: string;
  razorpayKeyId?: string;
  razorpayOrderId?: string;
  amountMinor?: number;
  currency?: string;
}

export interface PlacedOrder {
  id: string;
  reference: string;
  currencyCode: string;
  subtotalMinor: number;
  deliveryMinor: number;
  totalMinor: number;
  orderStatus: string;
  paymentStatus: string;
  payment?: OrderPayment;
}

export interface PaymentMethodsInfo {
  methods: string[];
  currency: string;
  codMaxMinor: number;
  razorpayKeyId: string;
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
  items: OrderLine[];
}

export interface ContactMessage {
  name: string;
  email: string;
  subject: string;
  message: string;
}

interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_URL) {
    throw new AuthError("Checkout needs the live API (set VITE_API_URL).", 503, "demo_mode");
  }
  const response = await fetch(`${API_URL}${path}`, {
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

export function placeOrder(
  items: CheckoutItem[],
  deliveryAddress: DeliveryAddress,
  paymentMethod: string = "cod",
): Promise<PlacedOrder> {
  return request<PlacedOrder>("/v1/public/checkout", {
    method: "POST",
    body: JSON.stringify({ items, deliveryAddress, paymentMethod }),
  });
}

interface RazorpayResult {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
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
    script.onerror = () => reject(new AuthError("Could not load the payment widget.", 502, "payment_error"));
    document.head.appendChild(script);
  });
}

/** Open Razorpay checkout for a pending order and resolve once the payment is
 *  verified server-side. Rejects if the customer dismisses the widget. */
export async function payWithRazorpay(
  order: PlacedOrder,
  prefill: { name: string; email: string },
): Promise<PlacedOrder & { ok: boolean }> {
  const payment = order.payment;
  if (!payment?.razorpayOrderId || !payment.razorpayKeyId) {
    throw new AuthError("The payment could not be started.", 500, "payment_error");
  }
  await loadRazorpayScript();
  const Razorpay = (window as unknown as { Razorpay: new (options: unknown) => { open: () => void } })
    .Razorpay;
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

export function listMyOrders(): Promise<OrderSummary[]> {
  return request<{ items: OrderSummary[] }>("/v1/public/orders").then((body) => body.items);
}

export function getMyOrder(reference: string): Promise<OrderDetail> {
  return request<OrderDetail>(`/v1/public/orders/${encodeURIComponent(reference)}`);
}

export function sendContactMessage(input: ContactMessage): Promise<{ ok: boolean; id: string }> {
  return request<{ ok: boolean; id: string }>("/v1/public/contact", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
