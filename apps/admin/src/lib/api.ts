/**
 * Admin API client.
 *
 * With `VITE_API_URL` set, requests hit the FastAPI admin endpoints with
 * credentials. Without it (demo-data mode) the client resolves the
 * deterministic fixture catalogue so the console is fully reviewable before
 * Cloudflare resources exist.
 */

import type {
  AdminCategoryRow,
  AdminInventoryRow,
  AdminOrderRow,
  AdminProductRow,
  AdminUserRow,
  AuditLogRow,
  ProductDetail,
  PublicPageBlock,
} from "@truegrit/contracts";
import {
  adminCategories,
  adminInventory,
  adminOrders,
  adminProducts,
  adminUsers,
  auditLog,
  homePage,
  products,
} from "@truegrit/contracts/fixtures";

const API_URL: string | undefined = import.meta.env.VITE_API_URL as string | undefined;

export const demoMode = !API_URL;

async function demo<T>(data: T): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, 120));
  return structuredClone(data);
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { credentials: "include" });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { code?: string; message?: string };
    } | null;
    throw new ApiError(
      body?.error?.message ?? `Request failed (${response.status})`,
      response.status,
      body?.error?.code ?? "request_failed",
    );
  }
  return (await response.json()) as T;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
  }
}

export interface Me {
  id: string;
  displayName: string;
  email: string;
  permissions: string[];
}

const DEMO_ME: Me = {
  id: "usr_admin",
  displayName: "Asha Rao",
  email: "admin@truegrit.test",
  permissions: [
    "products.view",
    "products.create",
    "products.edit",
    "products.approve",
    "products.publish",
    "categories.view",
    "categories.create",
    "categories.edit",
    "categories.approve",
    "categories.publish",
    "pages.view",
    "pages.edit",
    "pages.publish",
    "media.view",
    "media.upload",
    "orders.view",
    "orders.cancel",
    "orders.refund",
    "inventory.view",
    "inventory.adjust",
    "users.view",
    "users.invite",
    "users.manage_roles",
    "audit.view",
    "settings.view",
    "settings.edit",
  ],
};

export const api = {
  me: (): Promise<Me> => (demoMode ? demo(DEMO_ME) : get<Me>("/v1/admin/me")),

  products: (): Promise<AdminProductRow[]> =>
    demoMode
      ? demo(adminProducts)
      : get<{ items: AdminProductRow[] }>("/v1/admin/products").then((body) => body.items),

  productDetail: (id: string): Promise<ProductDetail | null> =>
    demo(products.find((product) => product.id === id) ?? null),

  categories: (): Promise<AdminCategoryRow[]> =>
    demoMode
      ? demo(adminCategories)
      : get<{ items: AdminCategoryRow[] }>("/v1/admin/categories").then((body) => body.items),

  inventory: (): Promise<AdminInventoryRow[]> =>
    demoMode
      ? demo(adminInventory)
      : get<{ items: AdminInventoryRow[] }>("/v1/admin/inventory").then((body) => body.items),

  orders: (): Promise<AdminOrderRow[]> => demo(adminOrders),

  users: (): Promise<AdminUserRow[]> => demo(adminUsers),

  audit: (): Promise<AuditLogRow[]> =>
    demoMode
      ? demo(auditLog)
      : get<{ items: AuditLogRow[] }>("/v1/admin/audit").then((body) => body.items),

  homeBlocks: (): Promise<PublicPageBlock[]> => demo(homePage.blocks),
};
