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

export interface PlacedOrder {
  id: string;
  reference: string;
  currencyCode: string;
  subtotalMinor: number;
  deliveryMinor: number;
  totalMinor: number;
  orderStatus: string;
  paymentStatus: string;
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

export function placeOrder(
  items: CheckoutItem[],
  deliveryAddress: DeliveryAddress,
): Promise<PlacedOrder> {
  return request<PlacedOrder>("/v1/public/checkout", {
    method: "POST",
    body: JSON.stringify({ items, deliveryAddress }),
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
