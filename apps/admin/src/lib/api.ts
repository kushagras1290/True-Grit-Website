/**
 * Admin API client.
 *
 * With `VITE_API_URL` set, requests hit the FastAPI admin endpoints with
 * credentials. Without it (demo-data mode) the client resolves the
 * deterministic fixture catalogue so the console is fully reviewable before
 * Cloudflare resources exist.
 */

import type {
  AdminArticleDetail,
  AdminArticleRow,
  AdminCategoryRow,
  AdminInventoryRow,
  AdminMediaAssetRow,
  AdminOrderRow,
  AdminProductRow,
  AdminRecipeDetail,
  AdminRecipeRow,
  AdminReturnRequestDetail,
  AdminReturnRequestRow,
  AdminUserRow,
  AuditLogRow,
  ContentBlock,
  PublicPageBlock,
  ReportDefinitionSummary,
  ReportRunResult,
} from "@truegrit/contracts";
import {
  adminCategories,
  adminInventory,
  adminOrders,
  adminProducts,
  adminUsers,
  articles as demoArticles,
  auditLog,
  homePage,
  products,
  recipes as demoRecipes,
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

async function postFile<T>(path: string, file: File): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": file.type || "application/octet-stream" },
    body: file,
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
  returnEligible: boolean;
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
  releaseScope: "global" | "selected";
  releaseCountries: string[];
  updatedAt: string;
}

export interface AdminRole {
  id: string;
  key: string;
  name: string;
  description: string;
  isSystem: boolean;
  locked: boolean;
  permissionIds: string[];
  permissionKeys: string[];
}

export interface AdminPermission {
  id: string;
  key: string;
  description: string;
}

export interface AdminFarmRow {
  id: string;
  name: string;
  slug: string;
  farmerName: string;
  region: string;
  countryCode: string;
  establishedYear: number | null;
  summary: string;
  status: string;
  productCount: number;
  updatedAt: string;
}

export interface AdminContactMessageRow {
  id: string;
  name: string;
  email: string;
  subject: string;
  message: string;
  status: "new" | "read" | "archived";
  createdAt: string;
  handledAt: string | null;
}

export type ArchiveKind = "product" | "category" | "farm" | "page";

export interface ArchiveRow {
  id: string;
  kind: ArchiveKind;
  name: string;
  slug: string;
  status: string;
  archivedAt: string;
  updatedAt: string;
  updatedBy: string;
  detail: string;
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
  heroImageUrl: string;
  heroImageAlt: string;
  heroSlides: Array<{
    imageUrl: string;
    imageAlt: string;
    href: string;
    label: string;
    enabled: boolean;
  }>;
  primaryActionLabel: string;
  primaryActionHref: string;
  secondaryActionLabel: string;
  secondaryActionHref: string;
  seoTitle: string;
  seoDescription: string;
  seoKeywords: string;
}

export interface SiteDocuments {
  robotsTxt: string;
  sitemapXml: string;
  llmsTxt: string;
}

export interface CmsPageRow {
  id: string;
  slug: string;
  title: string;
  pageType: string;
  templateKey: string;
  status: string;
  seoTitle: string;
  seoDescription: string;
  seoKeywords: string;
  indexingPolicy: "index" | "noindex";
  updatedAt: string;
  blockCount: number;
}

export interface CmsPageDetail extends CmsPageRow {
  blocks: PublicPageBlock[];
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
      returnEligible: true,
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

  archive: (): Promise<ArchiveRow[]> =>
    demoMode
      ? demo([
          {
            id: "demo_arch_product",
            kind: "product",
            name: "Archived sample product",
            slug: "archived-sample-product",
            status: "archived",
            archivedAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            updatedBy: "Demo Admin",
            detail: "Demo farm",
          },
        ])
      : get<{ items: ArchiveRow[] }>("/v1/admin/archive").then((body) => body.items),

  restoreArchiveItem: (
    kind: ArchiveKind,
    id: string,
  ): Promise<{ id: string; kind: ArchiveKind; status: string }> =>
    demoMode
      ? demo({ id, kind, status: "draft" })
      : post(`/v1/admin/archive/${kind}/${id}/restore`),

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
      releaseScope: "global",
      releaseCountries: [],
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

  clearInventory: (variantIds: string[]): Promise<{ clearedIds: string[]; count: number }> =>
    demoMode
      ? demo({ clearedIds: variantIds, count: variantIds.length })
      : post("/v1/admin/inventory/bulk-clear", {
          variantIds,
          note: "Bulk cleared from the admin inventory table.",
        }),

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

  permissions: (): Promise<AdminPermission[]> =>
    demoMode
      ? demo([])
      : get<{ items: AdminPermission[] }>("/v1/admin/permissions").then((body) => body.items),

  setRolePermissions: (
    id: string,
    permissionIds: string[],
  ): Promise<{ id: string; permissionIds: string[] }> =>
    demoMode ? demo({ id, permissionIds }) : patch(`/v1/admin/roles/${id}/permissions`, { permissionIds }),

  inviteUser: (input: {
    email: string;
    displayName: string;
    roleIds: string[];
  }): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id: `usr_${Date.now().toString(36)}`, status: "invited" })
      : post("/v1/admin/users/invite", input),

  createUser: (input: {
    email: string;
    displayName: string;
    roleIds: string[];
    password: string;
  }): Promise<{ id: string; email: string; status: string }> =>
    demoMode
      ? demo({ id: `usr_${Date.now().toString(36)}`, email: input.email, status: "active" })
      : post("/v1/admin/users", input),

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

  sendUserPasswordReset: (
    id: string,
  ): Promise<{ id: string; email: string; emailSent: boolean }> =>
    demoMode
      ? demo({ id, email: "user@demo.test", emailSent: true })
      : post(`/v1/admin/users/${id}/password-reset-email`),

  contactMessages: (): Promise<AdminContactMessageRow[]> =>
    demoMode
      ? demo([])
      : get<{ items: AdminContactMessageRow[] }>("/v1/admin/contact-messages").then(
          (body) => body.items,
        ),

  farms: (): Promise<AdminFarmRow[]> =>
    demoMode
      ? demo([
          {
            id: "farm_devika",
            name: "Devika Organics",
            slug: "devika-organics",
            farmerName: "Devika Kulkarni",
            region: "Ratnagiri, Maharashtra",
            countryCode: "IN",
            establishedYear: 1998,
            summary: "Ratnagiri mango orchards farmed without synthetic chemicals.",
            status: "published",
            productCount: 1,
            updatedAt: "2026-07-01T00:00:00Z",
          },
        ])
      : get<{ items: AdminFarmRow[] }>("/v1/admin/farms").then((body) => body.items),

  createFarm: (input: {
    name: string;
    slug?: string;
    farmerName: string;
    region: string;
    countryCode: string;
    establishedYear: number | null;
    summary: string;
    status: string;
  }): Promise<AdminFarmRow> =>
    demoMode
      ? demo({
          id: `farm_${Date.now().toString(36)}`,
          slug: input.slug || input.name.toLowerCase().replaceAll(" ", "-"),
          productCount: 0,
          updatedAt: new Date().toISOString(),
          ...input,
        })
      : post("/v1/admin/farms", input),

  updateFarm: (
    id: string,
    input: {
      name: string;
      slug?: string;
      farmerName: string;
      region: string;
      countryCode: string;
      establishedYear: number | null;
      summary: string;
      status: string;
    },
  ): Promise<AdminFarmRow> =>
    demoMode
      ? demo({
          id,
          productCount: 0,
          updatedAt: new Date().toISOString(),
          ...input,
          slug: input.slug || input.name.toLowerCase().replaceAll(" ", "-"),
        })
      : patch(`/v1/admin/farms/${id}`, input),

  deleteFarm: (
    id: string,
  ): Promise<{ id: string; status: string; archivedProductCount: number }> =>
    demoMode
      ? demo({ id, status: "archived", archivedProductCount: 0 })
      : del(`/v1/admin/farms/${id}`),

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
          heroImageUrl: "/homepage-hero.png",
          heroImageAlt: "Organic mangoes held in a sunlit orchard",
          heroSlides: [
            {
              imageUrl: "/homepage-hero.png",
              imageAlt: "Organic mangoes held in a sunlit orchard",
              href: "/shop",
              label: "Explore the market",
              enabled: true,
            },
            {
              imageUrl: "/homepage-hero-tomatoes.png",
              imageAlt: "Organic tomatoes harvested in a mountain field",
              href: "/category/organic-vegetables",
              label: "Shop vegetables",
              enabled: true,
            },
            {
              imageUrl: "/homepage-hero-roots.png",
              imageAlt: "Fresh carrots and beets pulled from organic soil",
              href: "/category/organic-vegetables",
              label: "Shop root vegetables",
              enabled: true,
            },
            {
              imageUrl: "/homepage-hero-greens.png",
              imageAlt: "Fresh leafy greens and herbs held in a farm field",
              href: "/category/organic-vegetables",
              label: "Shop fresh greens",
              enabled: true,
            },
            {
              imageUrl: "/homepage-hero-citrus.png",
              imageAlt: "Seasonal citrus and pears in an organic orchard",
              href: "/seasonal",
              label: "See seasonal fruit",
              enabled: true,
            },
          ],
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

  siteDocuments: (): Promise<SiteDocuments> =>
    demoMode
      ? demo({
          robotsTxt:
            "User-agent: *\nAllow: /\nDisallow: /checkout\nDisallow: /account\nDisallow: /payment/\n\nSitemap: http://localhost:5173/sitemap.xml\n",
          sitemapXml:
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <url><loc>http://localhost:5173/</loc></url>\n</urlset>\n',
          llmsTxt:
            "# True Grit\n\nTraceable organic food from verified farms.\n\n## Core Pages\n- Home: http://localhost:5173/\n- Shop: http://localhost:5173/shop\n",
        })
      : get<SiteDocuments>("/v1/admin/site-documents"),

  updateSiteDocuments: (input: Partial<SiteDocuments>): Promise<SiteDocuments> =>
    demoMode ? demo(input as SiteDocuments) : patch("/v1/admin/site-documents", input),

  cmsPages: (): Promise<CmsPageRow[]> =>
    demoMode
      ? demo([
          {
            id: homePage.id,
            slug: homePage.slug,
            title: homePage.title,
            pageType: "landing",
            templateKey: "modular",
            status: "published",
            seoTitle: homePage.seo.title,
            seoDescription: homePage.seo.description,
            seoKeywords: homePage.seo.keywords ?? "",
            indexingPolicy: homePage.seo.indexing,
            updatedAt: new Date().toISOString(),
            blockCount: homePage.blocks.length,
          },
        ])
      : get<{ items: CmsPageRow[] }>("/v1/admin/pages").then((body) => body.items),

  cmsPage: (id: string): Promise<CmsPageDetail> =>
    demoMode
      ? demo({
          id: homePage.id,
          slug: homePage.slug,
          title: homePage.title,
          pageType: "landing",
          templateKey: "modular",
          status: "published",
          seoTitle: homePage.seo.title,
          seoDescription: homePage.seo.description,
          seoKeywords: homePage.seo.keywords ?? "",
          indexingPolicy: homePage.seo.indexing,
          updatedAt: new Date().toISOString(),
          blockCount: homePage.blocks.length,
          blocks: homePage.blocks,
        })
      : get<CmsPageDetail>(`/v1/admin/pages/${id}`),

  updateCmsPage: (
    id: string,
    input: Partial<CmsPageDetail> & { changeSummary?: string },
  ): Promise<CmsPageDetail> =>
    demoMode ? demo({ ...(input as CmsPageDetail), id }) : patch(`/v1/admin/pages/${id}`, input),

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
      : postFile(`/v1/admin/media/images?filename=${encodeURIComponent(file.name)}`, file),

  homeBlocks: (): Promise<PublicPageBlock[]> => demo(homePage.blocks),

  // --- Articles (blog) -------------------------------------------------

  articles: (): Promise<AdminArticleRow[]> =>
    demoMode
      ? demo(
          demoArticles.map((article) => ({
            id: article.id,
            title: article.title,
            slug: article.slug,
            status: "published" as const,
            authorName: article.authorName,
            updatedAt: article.publishedAt,
            publishedAt: article.publishedAt,
            hasDraftChanges: false,
          })),
        )
      : get<{ items: AdminArticleRow[] }>("/v1/admin/articles").then((body) => body.items),

  getArticle: (id: string): Promise<AdminArticleDetail> => {
    if (!demoMode) return get<AdminArticleDetail>(`/v1/admin/articles/${id}`);
    const article = demoArticles.find((entry) => entry.id === id) ?? demoArticles[0]!;
    return demo<AdminArticleDetail>({
      id: article.id,
      title: article.title,
      slug: article.slug,
      excerpt: article.excerpt,
      readingMinutes: article.readingMinutes,
      status: "published",
      authorUserId: null,
      heroMediaId: null,
      seoTitle: article.seo.title,
      seoDescription: article.seo.description,
      seoKeywords: article.seo.keywords ?? "",
      canonicalUrl: article.seo.canonicalPath,
      indexingPolicy: article.seo.indexing,
      updatedAt: article.publishedAt,
      blocks: article.blocks,
      pullQuote: article.pullQuote,
    });
  },

  createArticle: (input: {
    title: string;
    slug?: string;
    excerpt?: string;
  }): Promise<{ id: string }> =>
    demoMode ? demo({ id: `art_${Date.now().toString(36)}` }) : post("/v1/admin/articles", input),

  updateArticle: (id: string, input: Record<string, unknown>): Promise<AdminArticleDetail> =>
    demoMode ? api.getArticle(id) : patch(`/v1/admin/articles/${id}`, input),

  submitArticle: (id: string): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: "in_review" })
      : post(`/v1/admin/articles/${id}/submit-for-review`),

  approveArticle: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "approved" }) : post(`/v1/admin/articles/${id}/approve`),

  requestArticleChanges: (id: string, note: string): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: "draft" })
      : post(`/v1/admin/articles/${id}/request-changes`, { note }),

  publishArticle: (id: string): Promise<{ id: string; status: string; version: number }> =>
    demoMode
      ? demo({ id, status: "published", version: 1 })
      : post(`/v1/admin/articles/${id}/publish`),

  unpublishArticle: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "unpublished" }) : post(`/v1/admin/articles/${id}/unpublish`),

  // --- Recipes -----------------------------------------------------------

  recipes: (): Promise<AdminRecipeRow[]> =>
    demoMode
      ? demo(
          demoRecipes.map((recipe) => ({
            id: recipe.id,
            title: recipe.title,
            slug: recipe.slug,
            status: "published" as const,
            chefName: "Demo Chef",
            updatedAt: new Date().toISOString(),
            publishedAt: new Date().toISOString(),
            hasDraftChanges: false,
          })),
        )
      : get<{ items: AdminRecipeRow[] }>("/v1/admin/recipes").then((body) => body.items),

  getRecipe: (id: string): Promise<AdminRecipeDetail> => {
    if (!demoMode) return get<AdminRecipeDetail>(`/v1/admin/recipes/${id}`);
    const recipe = demoRecipes.find((entry) => entry.id === id) ?? demoRecipes[0]!;
    return demo<AdminRecipeDetail>({
      id: recipe.id,
      title: recipe.title,
      slug: recipe.slug,
      excerpt: recipe.excerpt,
      prepMinutes: recipe.prepMinutes,
      cookMinutes: recipe.cookMinutes,
      servings: recipe.servings,
      dietaryTags: recipe.dietaryTags,
      status: "published",
      chefUserId: null,
      seoTitle: recipe.seo.title,
      seoDescription: recipe.seo.description,
      seoKeywords: recipe.seo.keywords ?? "",
      canonicalUrl: recipe.seo.canonicalPath,
      indexingPolicy: recipe.seo.indexing,
      updatedAt: new Date().toISOString(),
      blocks: recipe.blocks,
      steps: recipe.steps,
      ingredients: recipe.ingredients.map((ingredient, index) => ({
        id: `demo_ing_${index}`,
        label: ingredient.label,
        quantityText: ingredient.quantityText,
        productId: null,
        productSlug: ingredient.productSlug,
      })),
    });
  },

  createRecipe: (input: {
    title: string;
    slug?: string;
    excerpt?: string;
  }): Promise<{ id: string }> =>
    demoMode ? demo({ id: `rcp_${Date.now().toString(36)}` }) : post("/v1/admin/recipes", input),

  updateRecipe: (id: string, input: Record<string, unknown>): Promise<AdminRecipeDetail> =>
    demoMode ? api.getRecipe(id) : patch(`/v1/admin/recipes/${id}`, input),

  submitRecipe: (id: string): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: "in_review" })
      : post(`/v1/admin/recipes/${id}/submit-for-review`),

  approveRecipe: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "approved" }) : post(`/v1/admin/recipes/${id}/approve`),

  requestRecipeChanges: (id: string, note: string): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: "draft" })
      : post(`/v1/admin/recipes/${id}/request-changes`, { note }),

  publishRecipe: (id: string): Promise<{ id: string; status: string; version: number }> =>
    demoMode
      ? demo({ id, status: "published", version: 1 })
      : post(`/v1/admin/recipes/${id}/publish`),

  unpublishRecipe: (id: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: "unpublished" }) : post(`/v1/admin/recipes/${id}/unpublish`),

  // --- Return requests -----------------------------------------------------

  returns: (status?: string): Promise<AdminReturnRequestRow[]> =>
    demoMode
      ? demo([])
      : get<{ items: AdminReturnRequestRow[] }>(
          `/v1/admin/returns${status ? `?status=${encodeURIComponent(status)}` : ""}`,
        ).then((body) => body.items),

  getReturn: (id: string): Promise<AdminReturnRequestDetail> =>
    demoMode
      ? Promise.reject(new ApiError("Demo mode has no return requests yet.", 404, "not_found"))
      : get<AdminReturnRequestDetail>(`/v1/admin/returns/${id}`),

  decideReturn: (id: string, decision: string): Promise<{ id: string; status: string }> =>
    demoMode ? demo({ id, status: decision }) : post(`/v1/admin/returns/${id}/decide`, { decision }),

  resolveReturn: (
    id: string,
    input: { resolutionType: string; resolutionAmountMinor?: number | null; resolutionNotes?: string },
  ): Promise<{ id: string; status: string }> =>
    demoMode
      ? demo({ id, status: "completed" })
      : post(`/v1/admin/returns/${id}/resolve`, input),

  // --- Media library ---------------------------------------------------

  mediaLibrary: (): Promise<AdminMediaAssetRow[]> =>
    demoMode
      ? demo([])
      : get<{ items: AdminMediaAssetRow[] }>("/v1/admin/media").then((body) => body.items),

  updateMediaAsset: (
    id: string,
    input: { altText?: string; caption?: string },
  ): Promise<AdminMediaAssetRow> =>
    demoMode
      ? demo({
          id,
          url: "",
          originalFilename: "",
          mimeType: "image/png",
          sizeBytes: 0,
          widthPx: null,
          heightPx: null,
          altText: input.altText ?? "",
          caption: input.caption ?? "",
          createdAt: new Date().toISOString(),
        })
      : patch(`/v1/admin/media/${id}`, input),

  deleteMediaAsset: (id: string): Promise<{ id: string; deleted: boolean }> =>
    demoMode ? demo({ id, deleted: true }) : del(`/v1/admin/media/${id}`),

  // --- Owner reports console --------------------------------------------

  reports: (): Promise<ReportDefinitionSummary[]> =>
    demoMode ? demo([]) : get<{ items: ReportDefinitionSummary[] }>("/v1/admin/reports").then((body) => body.items),

  runReport: (id: string, filters: Record<string, string>): Promise<ReportRunResult> =>
    demoMode
      ? demo({ id, label: id, columns: [], rows: [] })
      : post(`/v1/admin/reports/${id}/run`, { filters }),

  // --- Category geo release ---------------------------------------------

  setCategoryRelease: (
    id: string,
    input: { releaseScope: "global" | "selected"; releaseCountries: string[] },
  ): Promise<{ id: string }> =>
    demoMode
      ? demo({ id })
      : patch(`/v1/admin/categories/${id}`, {
          releaseScope: input.releaseScope,
          releaseCountries: input.releaseCountries,
        }),
};

export type { ContentBlock };
