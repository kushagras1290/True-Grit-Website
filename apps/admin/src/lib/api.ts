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
const DEMO_AUTH_KEY = "truegrit.admin.session";
const DEMO_EMAIL = "admin@truegrit.test";
const DEMO_PASSWORD = "admin123";
export const ADMIN_AUTH_EXPIRED_EVENT = "truegrit.admin.auth-expired";

export const demoMode = !API_URL;

async function demo<T>(data: T): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, 120));
  return structuredClone(data);
}

async function fileToBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  let binary = "";
  const bytes = new Uint8Array(buffer);
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function notifyAuthExpired(path: string) {
  if (typeof window === "undefined") return;
  if (path === "/v1/admin/me" || path === "/v1/admin/auth/login") return;
  window.dispatchEvent(new CustomEvent(ADMIN_AUTH_EXPIRED_EVENT));
}

async function apiErrorFromResponse(response: Response, path: string): Promise<ApiError> {
  const body = (await response.json().catch(() => null)) as {
    error?: { code?: string; message?: string };
  } | null;
  if (response.status === 401) notifyAuthExpired(path);
  return new ApiError(
    body?.error?.message ?? `Request failed (${response.status})`,
    response.status,
    body?.error?.code ?? "request_failed",
  );
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { credentials: "include" });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  return (await response.json()) as T;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  return (await response.json()) as T;
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "PATCH",
    credentials: "include",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  return (await response.json()) as T;
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "PUT",
    credentials: "include",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  return (await response.json()) as T;
}

async function del<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
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

export interface AdminLinkedProduct {
  id: string;
  name: string;
  slug: string;
  status: string;
}

export interface AdminProductDetail {
  id: string;
  name: string;
  slug: string;
  shortDescription: string;
  productType: string;
  status: string;
  farmName: string;
  seoTitle: string;
  seoDescription: string;
  imageUrl: string;
  imageAlt: string;
  updatedAt: string;
  releaseScope: "global" | "selected";
  releaseCountries: string[];
  linkedProducts: AdminLinkedProduct[];
  variants: Array<{
    id: string;
    name: string;
    sku: string;
    status: string;
    listMinor: number | null;
    saleMinor: number | null;
    available: number;
  }>;
}

export interface AdminCategoryDetail {
  id: string;
  name: string;
  slug: string;
  shortDescription: string;
  heroEyebrow: string;
  heroTitle: string;
  heroDescription: string;
  seasonLabel: string;
  themeKey: string;
  visibility: string;
  status: string;
  seoTitle: string;
  seoDescription: string;
  heroImageUrl: string;
  heroImageAlt: string;
  productAssignmentMode: string;
  updatedAt: string;
}

export interface AdminRole {
  id: string;
  key: string;
  name: string;
  description: string;
}

export interface AdminOrderDetail {
  id: string;
  publicReference: string;
  customerEmail: string;
  currencyCode: string;
  subtotalMinor: number;
  discountMinor: number;
  deliveryMinor: number;
  taxMinor: number;
  totalMinor: number;
  orderStatus: string;
  paymentStatus: string;
  fulfilmentStatus: string;
  deliveryStatus: string;
  placedAt: string;
  items: Array<{
    id: string;
    productName: string;
    variantName: string;
    sku: string;
    quantity: number;
    unitMinor: number;
    lineTotalMinor: number;
  }>;
}

export interface Me {
  id: string;
  displayName: string;
  email: string;
  permissions: string[];
  farmId?: string | null;
  farmName?: string | null;
}

export interface SiteControl {
  announcementActive: boolean;
  announcementMessage: string;
  announcementPath: string;
  heroEyebrow: string;
  heroHeading: string;
  heroText: string;
  primaryActionLabel: string;
  primaryActionHref: string;
  secondaryActionLabel: string;
  secondaryActionHref: string;
  seoTitle: string;
  seoDescription: string;
  seoKeywords: string;
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

function hasDemoSession(): boolean {
  return typeof window !== "undefined" && window.localStorage.getItem(DEMO_AUTH_KEY) === "active";
}

function setDemoSession(active: boolean): void {
  if (typeof window === "undefined") return;
  if (active) {
    window.localStorage.setItem(DEMO_AUTH_KEY, "active");
  } else {
    window.localStorage.removeItem(DEMO_AUTH_KEY);
  }
}

export const api = {
  me: async (): Promise<Me> => {
    if (!demoMode) return get<Me>("/v1/admin/me");
    if (!hasDemoSession()) {
      throw new ApiError("Authentication required.", 401, "authentication_required");
    }
    return demo(DEMO_ME);
  },

  login: async (email: string, password: string): Promise<void> => {
    if (demoMode) {
      await new Promise((resolve) => setTimeout(resolve, 180));
      if (email.toLowerCase() !== DEMO_EMAIL || password !== DEMO_PASSWORD) {
        throw new ApiError("Invalid admin email or password.", 401, "authentication_required");
      }
      setDemoSession(true);
      return;
    }
    await post<{ ok: boolean }>("/v1/admin/auth/login", { email, password });
  },

  logout: async (): Promise<void> => {
    if (demoMode) {
      setDemoSession(false);
      return;
    }
    await post<{ ok: boolean }>("/v1/admin/auth/logout");
  },

  products: (): Promise<AdminProductRow[]> =>
    demoMode
      ? demo(adminProducts)
      : get<{ items: AdminProductRow[] }>("/v1/admin/products").then((body) => body.items),

  getProduct: (id: string): Promise<AdminProductDetail> => {
    if (!demoMode) return get<AdminProductDetail>(`/v1/admin/products/${id}`);
    const product = products.find((entry) => entry.id === id);
    if (!product) throw new ApiError("Product not found.", 404, "not_found");
    return demo<AdminProductDetail>({
      id: product.id,
      name: product.name,
      slug: product.slug,
      shortDescription: product.shortDescription,
      productType: "general",
      status: "published",
      farmName: product.farmName,
      seoTitle: product.seo.title,
      seoDescription: product.seo.description,
      imageUrl: product.imageUrl ?? "",
      imageAlt: product.imageAlt,
      updatedAt: new Date().toISOString(),
      releaseScope: "global",
      releaseCountries: [],
      linkedProducts: [],
      variants: product.variants.map((variant) => ({
        id: variant.id,
        name: variant.name,
        sku: variant.sku,
        status: "active",
        listMinor: variant.listMinor,
        saleMinor: variant.saleMinor,
        available: 0,
      })),
    });
  },

  createProduct: (input: {
    name: string;
    productType: string;
    slug?: string;
    shortDescription?: string;
  }): Promise<{ id: string; slug: string; status: string }> =>
    demoMode
      ? demo({
          id: `prd_${Date.now().toString(36)}`,
          slug: input.slug ?? "new-product",
          status: "draft",
        })
      : post("/v1/admin/products", input),

  updateProduct: (id: string, input: Record<string, unknown>): Promise<{ id: string }> =>
    demoMode ? demo({ id }) : patch(`/v1/admin/products/${id}`, input),

  publishProduct: (
    id: string,
    changeSummary?: string,
  ): Promise<{ status: string; version: number }> =>
    demoMode
      ? demo({ status: "published", version: 1 })
      : post(`/v1/admin/products/${id}/publish`, { changeSummary }),

  archiveProduct: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "archived" }) : post(`/v1/admin/products/${id}/archive`),

  deleteProduct: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "archived" }) : del(`/v1/admin/products/${id}`),

  deleteProducts: (productIds: string[]): Promise<{ deletedIds: string[]; count: number }> =>
    demoMode
      ? demo({ deletedIds: productIds, count: productIds.length })
      : post("/v1/admin/products/bulk-delete", { productIds }),

  categories: (): Promise<AdminCategoryRow[]> =>
    demoMode
      ? demo(adminCategories)
      : get<{ items: AdminCategoryRow[] }>("/v1/admin/categories").then((body) => body.items),

  getCategory: (id: string): Promise<AdminCategoryDetail> => {
    if (!demoMode) return get<AdminCategoryDetail>(`/v1/admin/categories/${id}`);
    const category = adminCategories.find((entry) => entry.id === id);
    if (!category) throw new ApiError("Category not found.", 404, "not_found");
    return demo<AdminCategoryDetail>({
      id: category.id,
      name: category.name,
      slug: category.slug,
      shortDescription: "",
      heroEyebrow: "",
      heroTitle: category.name,
      heroDescription: "",
      seasonLabel: "",
      themeKey: "forest",
      visibility: category.visibility,
      status: category.status,
      seoTitle: "",
      seoDescription: "",
      heroImageUrl: "",
      heroImageAlt: category.name,
      productAssignmentMode: "manual",
      updatedAt: category.updatedAt,
    });
  },

  createCategory: (input: {
    name: string;
    slug?: string;
    shortDescription?: string;
    heroTitle?: string;
    heroDescription?: string;
  }): Promise<{ id: string; slug: string; status: string }> =>
    demoMode
      ? demo({
          id: `cat_${Date.now().toString(36)}`,
          slug: input.slug ?? "new-category",
          status: "draft",
        })
      : post("/v1/admin/categories", input),

  updateCategory: (id: string, input: Record<string, unknown>): Promise<{ id: string }> =>
    demoMode ? demo({ id }) : patch(`/v1/admin/categories/${id}`, input),

  publishCategory: (id: string): Promise<{ status: string; version: number }> =>
    demoMode
      ? demo({ status: "published", version: 1 })
      : post(`/v1/admin/categories/${id}/publish`),

  deleteCategory: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "archived" }) : del(`/v1/admin/categories/${id}`),

  deleteCategories: (categoryIds: string[]): Promise<{ deletedIds: string[]; count: number }> =>
    demoMode
      ? demo({ deletedIds: categoryIds, count: categoryIds.length })
      : post("/v1/admin/categories/bulk-delete", { categoryIds }),

  inventory: (): Promise<AdminInventoryRow[]> =>
    demoMode
      ? demo(adminInventory)
      : get<{ items: AdminInventoryRow[] }>("/v1/admin/inventory").then((body) => body.items),

  adjustInventory: (input: {
    variantId?: string;
    sku?: string;
    quantityDelta: number;
    reasonCode: string;
    note: string;
  }): Promise<{ onHand: number; available: number }> =>
    demoMode ? demo({ onHand: 0, available: 0 }) : post("/v1/admin/inventory/adjustments", input),

  orders: (): Promise<AdminOrderRow[]> =>
    demoMode
      ? demo(adminOrders)
      : get<{ items: AdminOrderRow[] }>("/v1/admin/orders").then((body) => body.items),

  getOrder: (id: string): Promise<AdminOrderDetail> => {
    if (!demoMode) return get<AdminOrderDetail>(`/v1/admin/orders/${id}`);
    const order = adminOrders.find((entry) => entry.id === id);
    if (!order) throw new ApiError("Order not found.", 404, "not_found");
    return demo<AdminOrderDetail>({
      id: order.id,
      publicReference: order.publicReference,
      customerEmail: order.customerEmail,
      currencyCode: order.currencyCode,
      subtotalMinor: order.totalMinor,
      discountMinor: 0,
      deliveryMinor: 0,
      taxMinor: 0,
      totalMinor: order.totalMinor,
      orderStatus: order.orderStatus,
      paymentStatus: order.paymentStatus,
      fulfilmentStatus: order.fulfilmentStatus,
      deliveryStatus: "not_ready",
      placedAt: order.placedAt,
      items: [],
    });
  },

  updateOrderStatus: (id: string, status: string): Promise<{ orderStatus: string }> =>
    demoMode ? demo({ orderStatus: status }) : patch(`/v1/admin/orders/${id}/status`, { status }),

  users: (): Promise<AdminUserRow[]> =>
    demoMode
      ? demo(adminUsers)
      : get<{ items: AdminUserRow[] }>("/v1/admin/users").then((body) => body.items),

  roles: (): Promise<AdminRole[]> =>
    demoMode ? demo([]) : get<{ items: AdminRole[] }>("/v1/admin/roles").then((body) => body.items),

  inviteUser: (input: {
    email: string;
    displayName: string;
    roleIds: string[];
  }): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id: `usr_${Date.now().toString(36)}`, status: "invited" })
      : post("/v1/admin/users/invite", input),

  setUserStatus: (id: string, status: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status }) : patch(`/v1/admin/users/${id}/status`, { status }),

  setUserRoles: (id: string, roleIds: string[]): Promise<{ id: string }> =>
    demoMode ? demo({ id }) : patch(`/v1/admin/users/${id}/roles`, { roleIds }),

  deleteUser: (id: string): Promise<{ deletedIds: string[]; count: number }> =>
    demoMode ? demo({ deletedIds: [id], count: 1 }) : del(`/v1/admin/users/${id}`),

  deleteUsers: (userIds: string[]): Promise<{ deletedIds: string[]; count: number }> =>
    demoMode
      ? demo({ deletedIds: userIds, count: userIds.length })
      : post("/v1/admin/users/bulk-delete", { userIds }),

  resetFarmOwnerPassword: (
    id: string,
  ): Promise<{ id: string; email: string; temporaryPassword: string }> =>
    demoMode
      ? demo({ id, email: "owner@demo.test", temporaryPassword: "TempOwner-123456" })
      : post(`/v1/admin/users/${id}/temporary-password`),

  farms: (): Promise<Array<{ id: string; name: string }>> =>
    demoMode
      ? demo([{ id: "farm_devika", name: "Devika Organics" }])
      : get<{ items: Array<{ id: string; name: string }> }>("/v1/admin/farms").then(
          (body) => body.items,
        ),

  createFarmOwner: (input: {
    email: string;
    displayName: string;
    farmId: string;
    password: string;
  }): Promise<{ id: string; farmName: string }> =>
    demoMode
      ? demo({ id: `usr_${Date.now().toString(36)}`, farmName: "Demo Farm" })
      : post("/v1/admin/farm-owners", input),

  changePassword: async (
    currentPassword: string,
    newPassword: string,
  ): Promise<{ ok: boolean }> => {
    if (demoMode) {
      await new Promise((resolve) => setTimeout(resolve, 180));
      if (currentPassword !== DEMO_PASSWORD) {
        throw new ApiError("Current password is incorrect.", 401, "authentication_required");
      }
      // Demo mode has no backend to store it — say so rather than pretend.
      throw new ApiError(
        "Demo mode cannot change a password. Connect the API with VITE_API_URL.",
        422,
        "validation_error",
      );
    }
    return post("/v1/admin/auth/change-password", { currentPassword, newPassword });
  },

  requestPasswordReset: (email: string): Promise<{ ok: boolean }> =>
    demoMode ? demo({ ok: true }) : post("/v1/admin/auth/password-reset", { email }),

  confirmPasswordReset: (token: string, newPassword: string): Promise<{ ok: boolean }> =>
    demoMode
      ? demo({ ok: true })
      : post("/v1/admin/auth/password-reset/confirm", { token, newPassword }),

  audit: (): Promise<AuditLogRow[]> =>
    demoMode
      ? demo(auditLog)
      : get<{ items: AuditLogRow[] }>("/v1/admin/audit").then((body) => body.items),

  siteControl: (): Promise<SiteControl> =>
    demoMode
      ? demo({
          announcementActive: true,
          announcementMessage: "Alphonso season is here - orchard-fresh boxes ship every Tuesday.",
          announcementPath: "/seasonal",
          heroEyebrow: "Certified organic. Fully traceable.",
          heroHeading: "Food grown the way nature intended.",
          heroText: "Fresh organic produce, conscious pantry essentials and trusted local farms.",
          primaryActionLabel: "Explore the market",
          primaryActionHref: "/shop",
          secondaryActionLabel: "See what is in season",
          secondaryActionHref: "/seasonal",
          seoTitle: "True Grit - traceable organic food from verified farms",
          seoDescription: "Fresh organic produce and trusted local farms.",
          seoKeywords: "organic food, traceable produce, Indian farms",
        })
      : get<SiteControl>("/v1/admin/site-control"),

  updateSiteControl: (input: Partial<SiteControl>): Promise<SiteControl> =>
    demoMode ? demo(input as SiteControl) : patch("/v1/admin/site-control", input),

  highlights: (): Promise<AdminLinkedProduct[]> =>
    demoMode
      ? demo(
          products
            .slice(0, 4)
            .map((p) => ({ id: p.id, name: p.name, slug: p.slug, status: "published" })),
        )
      : get<{ items: AdminLinkedProduct[] }>("/v1/admin/highlights").then((body) => body.items),

  setHighlights: (productIds: string[]): Promise<AdminLinkedProduct[]> =>
    demoMode
      ? demo(
          products
            .filter((p) => productIds.includes(p.id))
            .map((p) => ({ id: p.id, name: p.name, slug: p.slug, status: "published" })),
        )
      : put<{ items: AdminLinkedProduct[] }>("/v1/admin/highlights", { productIds }).then(
          (body) => body.items,
        ),

  uploadImage: async (file: File): Promise<{ id: string; url: string }> =>
    demoMode
      ? demo({ id: `img_${Date.now().toString(36)}`, url: URL.createObjectURL(file) })
      : post("/v1/admin/media/images", {
          filename: file.name,
          contentType: file.type,
          dataBase64: await fileToBase64(file),
        }),

  homeBlocks: (): Promise<PublicPageBlock[]> => demo(homePage.blocks),
};
