/** Inventory (persisted adjustments), orders (with detail + status transitions),
 * users & roles (invite, enable/disable, role assignment), media, audit log. */

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AdminMediaAssetRow, AdminUserRow } from "@truegrit/contracts";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router";
import { z } from "zod";

import {
  Button,
  ConfirmDialog,
  DataTableShell,
  EmptyState,
  Field,
  ImagePreview,
  Input,
  LoadingRows,
  Modal,
  PageHeader,
  Pagination,
  SearchBox,
  Select,
  StatusPill,
  Td,
  Textarea,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import {
  ApiError,
  api,
  type AdminContactMessageRow,
  type AdminFarmRow,
  type AdminOrderDetail,
  type AdminRole,
} from "../lib/api";
import { formatDateTime, formatMoney } from "../lib/format";
import { PermissionGate } from "../lib/permissions";
import { ManageRolesModal } from "./scopes";

// ---------------------------------------------------------------------------
// Inventory
// ---------------------------------------------------------------------------

const adjustmentSchema = z.object({
  sku: z.string().min(1, "Pick a variant"),
  quantityDelta: z.coerce
    .number()
    .int("Whole units only")
    .refine((value) => value !== 0, "Delta cannot be zero"),
  reasonCode: z.enum(["receipt", "manual_adjustment", "write_off", "correction"], {
    message: "Choose a reason",
  }),
  note: z.string().min(5, "A human note is required for the audit trail").max(300),
});

type AdjustmentForm = z.infer<typeof adjustmentSchema>;

const farmSchema = z.object({
  name: z.string().min(3, "Enter a farm name").max(140),
  slug: z
    .string()
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Lowercase letters, numbers and single hyphens")
    .optional()
    .or(z.literal("")),
  farmerName: z.string().max(140),
  region: z.string().max(180),
  countryCode: z.string().length(2, "Use a 2-letter country code"),
  establishedYear: z.coerce.number().int().min(1800).max(2100).optional().or(z.literal("")),
  summary: z.string().max(500),
  status: z.enum(["draft", "published", "unpublished"]),
});

type FarmForm = z.infer<typeof farmSchema>;

export function InventoryPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const limit = 25;
  const offset = (page - 1) * limit;
  const { data, isLoading } = useQuery({
    queryKey: ["inventory", page, searchQuery],
    queryFn: () => api.inventory({ limit, offset, search: searchQuery || undefined }),
  });
  const [selectedVariantIds, setSelectedVariantIds] = useState<string[]>([]);
  const [confirmingClear, setConfirmingClear] = useState(false);

  const form = useForm<AdjustmentForm>({
    resolver: zodResolver(adjustmentSchema),
    defaultValues: { sku: "", quantityDelta: 0, reasonCode: "receipt", note: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: AdjustmentForm) =>
      api.adjustInventory({
        sku: values.sku,
        quantityDelta: values.quantityDelta,
        reasonCode: values.reasonCode,
        note: values.note,
      }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["inventory"] });
      toast.success(`Stock updated — ${result.onHand} on hand (${result.available} available).`);
      form.reset({ sku: "", quantityDelta: 0, reasonCode: "receipt", note: "" });
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not record the adjustment."),
  });
  const clearMutation = useMutation({
    mutationFn: (variantIds: string[]) => api.clearInventory(variantIds),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["inventory"] });
      setSelectedVariantIds([]);
      setConfirmingClear(false);
      toast.success(`${result.count} inventory row${result.count === 1 ? "" : "s"} cleared.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not clear inventory rows."),
  });

  const rows = data ?? [];
  const allSelected = rows.length > 0 && selectedVariantIds.length === rows.length;

  function toggleInventoryRow(variantId: string) {
    setSelectedVariantIds((current) =>
      current.includes(variantId)
        ? current.filter((id) => id !== variantId)
        : [...current, variantId],
    );
  }

  function toggleAllInventoryRows() {
    setSelectedVariantIds(allSelected ? [] : rows.map((row) => row.variantId));
  }

  return (
    <div>
      <PageHeader
        title="Inventory"
        description="Available is always derived (on hand − reserved). Every change is a movement."
        actions={
          selectedVariantIds.length > 0 ? (
            <PermissionGate permission="inventory.adjust">
              <Button
                variant="destructive"
                disabled={clearMutation.isPending}
                onClick={() => setConfirmingClear(true)}
              >
                Delete selected ({selectedVariantIds.length})
              </Button>
            </PermissionGate>
          ) : null
        }
      />
      {confirmingClear ? (
        <ConfirmDialog
          title={
            selectedVariantIds.length === 1
              ? "Delete inventory row"
              : `Delete ${selectedVariantIds.length} inventory rows`
          }
          description="Selected rows will be cleared to reserved stock, making available stock zero while preserving reservations, movement history and audit logs."
          confirmLabel="Delete selected"
          pendingLabel="Deleting..."
          isPending={clearMutation.isPending}
          onCancel={() => setConfirmingClear(false)}
          onConfirm={() => clearMutation.mutate(selectedVariantIds)}
        />
      ) : null}
      <div className="mb-4 max-w-sm">
        <SearchBox
          value={searchQuery}
          onSearch={(value) => {
            setSearchQuery(value);
            setPage(1);
          }}
          placeholder="Search by product or SKU..."
          aria-label="Search inventory"
        />
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <DataTableShell>
          <thead className="bg-canvas">
            <tr>
              <Th>
                <input
                  type="checkbox"
                  aria-label="Select all inventory rows"
                  checked={allSelected}
                  onChange={toggleAllInventoryRows}
                />
              </Th>
              <Th>Product</Th>
              <Th>Variant</Th>
              <Th>SKU</Th>
              <Th>On hand</Th>
              <Th>Reserved</Th>
              <Th>Available</Th>
              <Th>Stock Status</Th>
              <Th>Product Status</Th>
            </tr>
          </thead>
          {isLoading ? (
            <LoadingRows columns={9} />
          ) : (
            <tbody>
              {rows.map((row) => {
                const available = row.onHand - row.reserved;
                const status =
                  available <= 0
                    ? "out_of_stock"
                    : available <= row.reorderThreshold
                      ? "low_stock"
                      : "in_stock";
                return (
                  <tr key={row.variantId} className="border-t border-line">
                    <Td>
                      <input
                        type="checkbox"
                        aria-label={`Select ${row.productName} ${row.variantName}`}
                        checked={selectedVariantIds.includes(row.variantId)}
                        onChange={() => toggleInventoryRow(row.variantId)}
                      />
                    </Td>
                    <Td className="font-medium">{row.productName}</Td>
                    <Td className="text-ink-muted">{row.variantName}</Td>
                    <Td>{row.sku}</Td>
                    <Td>{row.onHand}</Td>
                    <Td>{row.reserved}</Td>
                    <Td className="font-medium">{available}</Td>
                    <Td>
                      <StatusPill status={status} />
                    </Td>
                    <Td>
                      <div className="flex items-center gap-2">
                        <StatusPill status={row.productStatus} />
                        <PermissionGate permission="products.publish">
                          <Button
                            variant="secondary"
                            onClick={() => {
                              const nextStatus =
                                row.productStatus === "published" ? "unpublished" : "published";
                              api
                                .updateProductStatus(row.productId, nextStatus)
                                .then(() => {
                                  toast.success("Product status updated.");
                                  queryClient.invalidateQueries({ queryKey: ["inventory"] });
                                })
                                .catch((error) => {
                                  toast.error(
                                    error instanceof ApiError
                                      ? error.message
                                      : "Failed to update product.",
                                  );
                                });
                            }}
                          >
                            {row.productStatus === "published" ? "Disable" : "Enable"}
                          </Button>
                        </PermissionGate>
                      </div>
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          )}
        </DataTableShell>
        <Pagination page={page} onPageChange={setPage} rowCount={rows.length} limit={limit} />

        <PermissionGate
          permission="inventory.adjust"
          fallback={
            <EmptyState
              title="Adjustments restricted"
              hint="Requires the inventory.adjust permission."
            />
          }
        >
          <form
            aria-label="Record inventory adjustment"
            className="h-fit space-y-4 rounded-md border border-line bg-surface p-4 shadow-card"
            onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
          >
            <h2 className="font-display text-lg text-ink">Record adjustment</h2>
            <Field label="Variant (SKU)" htmlFor="sku" error={form.formState.errors.sku?.message}>
              <Select id="sku" {...form.register("sku")}>
                <option value="">Select a variant…</option>
                {(data ?? []).map((row) => (
                  <option key={row.variantId} value={row.sku}>
                    {row.sku} — {row.productName} ({row.variantName})
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label="Quantity delta (+/−)"
              htmlFor="quantityDelta"
              error={form.formState.errors.quantityDelta?.message}
            >
              <Input id="quantityDelta" type="number" {...form.register("quantityDelta")} />
            </Field>
            <Field
              label="Reason"
              htmlFor="reasonCode"
              error={form.formState.errors.reasonCode?.message}
            >
              <Select id="reasonCode" {...form.register("reasonCode")}>
                <option value="receipt">Receipt</option>
                <option value="manual_adjustment">Manual adjustment</option>
                <option value="write_off">Write off</option>
                <option value="correction">Correction</option>
              </Select>
            </Field>
            <Field
              label="Note (required)"
              htmlFor="note"
              error={form.formState.errors.note?.message}
            >
              <Textarea id="note" placeholder="Why is stock changing?" {...form.register("note")} />
            </Field>
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "Recording…" : "Record movement"}
            </Button>
          </form>
        </PermissionGate>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Farms
// ---------------------------------------------------------------------------

function FarmModal({ farm, onClose }: { farm?: AdminFarmRow; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const form = useForm<FarmForm>({
    resolver: zodResolver(farmSchema),
    defaultValues: {
      name: farm?.name ?? "",
      slug: farm?.slug ?? "",
      farmerName: farm?.farmerName ?? "",
      region: farm?.region ?? "",
      countryCode: farm?.countryCode ?? "IN",
      establishedYear: farm?.establishedYear ?? "",
      summary: farm?.summary ?? "",
      status: (farm?.status as FarmForm["status"]) ?? "published",
    },
  });

  const mutation = useMutation({
    mutationFn: (values: FarmForm) =>
      farm
        ? api.updateFarm(farm.id, {
            name: values.name,
            slug: values.slug || undefined,
            farmerName: values.farmerName,
            region: values.region,
            countryCode: values.countryCode.toUpperCase(),
            establishedYear:
              typeof values.establishedYear === "number" ? values.establishedYear : null,
            summary: values.summary,
            status: values.status,
          })
        : api.createFarm({
            name: values.name,
            slug: values.slug || undefined,
            farmerName: values.farmerName,
            region: values.region,
            countryCode: values.countryCode.toUpperCase(),
            establishedYear:
              typeof values.establishedYear === "number" ? values.establishedYear : null,
            summary: values.summary,
            status: values.status,
          }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["farms"] }),
        queryClient.invalidateQueries({ queryKey: ["users"] }),
      ]);
      toast.success(farm ? "Farm updated." : "Farm created.");
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the farm."),
  });

  return (
    <Modal title={farm ? "Edit farm" : "New farm"} onClose={onClose}>
      <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Farm name" htmlFor="farm-name" error={form.formState.errors.name?.message}>
          <Input id="farm-name" placeholder="Devika Organics" {...form.register("name")} />
        </Field>
        <Field
          label="Slug (optional)"
          htmlFor="farm-slug"
          error={form.formState.errors.slug?.message}
        >
          <Input id="farm-slug" placeholder="devika-organics" {...form.register("slug")} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Farmer name"
            htmlFor="farm-farmer"
            error={form.formState.errors.farmerName?.message}
          >
            <Input id="farm-farmer" placeholder="Asha Rao" {...form.register("farmerName")} />
          </Field>
          <Field label="Region" htmlFor="farm-region" error={form.formState.errors.region?.message}>
            <Input
              id="farm-region"
              placeholder="Ratnagiri, Maharashtra"
              {...form.register("region")}
            />
          </Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field
            label="Country"
            htmlFor="farm-country"
            error={form.formState.errors.countryCode?.message}
          >
            <Input id="farm-country" maxLength={2} {...form.register("countryCode")} />
          </Field>
          <Field
            label="Established"
            htmlFor="farm-established"
            error={form.formState.errors.establishedYear?.message}
          >
            <Input id="farm-established" type="number" {...form.register("establishedYear")} />
          </Field>
          <Field label="Status" htmlFor="farm-status">
            <Select id="farm-status" {...form.register("status")}>
              <option value="published">Published</option>
              <option value="draft">Draft</option>
              <option value="unpublished">Unpublished</option>
            </Select>
          </Field>
        </div>
        <Field
          label="Farm summary"
          htmlFor="farm-summary"
          error={form.formState.errors.summary?.message}
        >
          <Textarea
            id="farm-summary"
            placeholder="Short public story for this farm."
            {...form.register("summary")}
          />
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Saving..." : farm ? "Save farm" : "Create farm"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function FarmsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const limit = 25;
  const offset = (page - 1) * limit;
  const { data, isLoading } = useQuery({
    queryKey: ["farms", page, searchQuery],
    queryFn: () => api.farms({ limit, offset, search: searchQuery || undefined }),
  });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<AdminFarmRow | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState<AdminFarmRow | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (farmId: string) => api.deleteFarm(farmId),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
      setConfirmingDelete(null);
      toast.success(
        result.archivedProductCount > 0
          ? `Farm deleted and ${result.archivedProductCount} product${result.archivedProductCount === 1 ? "" : "s"} archived.`
          : "Farm deleted from active list.",
      );
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete the farm."),
  });

  return (
    <div>
      <PageHeader
        title="Farms"
        description="Create partner farms before assigning products or farm-owner accounts."
        actions={
          <PermissionGate permission="users.invite">
            <Button variant="primary" onClick={() => setCreating(true)}>
              New farm
            </Button>
          </PermissionGate>
        }
      />
      {creating ? <FarmModal onClose={() => setCreating(false)} /> : null}
      {editing ? <FarmModal farm={editing} onClose={() => setEditing(null)} /> : null}
      {confirmingDelete ? (
        <ConfirmDialog
          title="Delete farm"
          description={
            confirmingDelete.productCount > 0
              ? `${confirmingDelete.name} has ${confirmingDelete.productCount} active product${confirmingDelete.productCount === 1 ? "" : "s"}. Deleting this farm will also archive those products and remove them from the storefront.`
              : `${confirmingDelete.name} will be removed from the active farm list.`
          }
          confirmLabel={
            confirmingDelete.productCount > 0 ? "Delete farm and products" : "Delete farm"
          }
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmingDelete(null)}
          onConfirm={() => deleteMutation.mutate(confirmingDelete.id)}
        />
      ) : null}
      <div className="mb-4 max-w-sm">
        <SearchBox
          value={searchQuery}
          onSearch={(value) => {
            setSearchQuery(value);
            setPage(1);
          }}
          placeholder="Search by farm or farmer name..."
          aria-label="Search farms"
        />
      </div>
      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Farm</Th>
            <Th>Slug</Th>
            <Th>Region</Th>
            <Th>Products</Th>
            <Th>Status</Th>
            <Th>Updated</Th>
            <Th>Actions</Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={7} />
        ) : (
          <tbody>
            {(data ?? []).map((farm) => (
              <tr key={farm.id} className="border-t border-line">
                <Td>
                  <div className="font-medium text-ink">{farm.name}</div>
                  <div className="text-xs text-ink-muted">
                    {farm.farmerName || "No farmer name"}
                  </div>
                </Td>
                <Td className="text-ink-muted">/{farm.slug}</Td>
                <Td>{farm.region || "—"}</Td>
                <Td>{farm.productCount}</Td>
                <Td>
                  <StatusPill status={farm.status} />
                </Td>
                <Td>{formatDateTime(farm.updatedAt)}</Td>
                <Td>
                  <PermissionGate permission="users.invite">
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" variant="secondary" onClick={() => setEditing(farm)}>
                        Alter
                      </Button>
                      <Button
                        type="button"
                        variant="destructive"
                        onClick={() => setConfirmingDelete(farm)}
                        disabled={deleteMutation.isPending}
                      >
                        Delete
                      </Button>
                    </div>
                  </PermissionGate>
                </Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      <Pagination page={page} onPageChange={setPage} rowCount={(data ?? []).length} limit={limit} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Orders
// ---------------------------------------------------------------------------

export function OrdersPage() {
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const limit = 25;
  const offset = (page - 1) * limit;
  const { data, isLoading } = useQuery({
    queryKey: ["orders", page, searchQuery],
    queryFn: () => api.orders({ limit, offset, search: searchQuery || undefined }),
  });

  return (
    <div>
      <PageHeader
        title="Orders"
        description="Snapshots at purchase time — catalogue edits never rewrite an order."
      />
      <div className="mb-4 max-w-sm">
        <SearchBox
          value={searchQuery}
          onSearch={(value) => {
            setSearchQuery(value);
            setPage(1);
          }}
          placeholder="Search by reference or customer email..."
          aria-label="Search orders"
        />
      </div>
      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Reference</Th>
            <Th>Customer</Th>
            <Th>Total</Th>
            <Th>Order</Th>
            <Th>Payment</Th>
            <Th>Fulfilment</Th>
            <Th>Placed</Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={7} />
        ) : (
          <tbody>
            {(data ?? []).map((order) => (
              <tr key={order.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <Link
                    to={`/orders/${order.id}`}
                    className="font-medium text-brand hover:underline"
                  >
                    {order.publicReference}
                  </Link>
                </Td>
                <Td className="text-ink-muted">{order.customerEmail}</Td>
                <Td>{formatMoney(order.totalMinor, order.currencyCode)}</Td>
                <Td>
                  <StatusPill status={order.orderStatus} />
                </Td>
                <Td>
                  <StatusPill status={order.paymentStatus} />
                </Td>
                <Td className="text-ink-muted">{order.fulfilmentStatus.replaceAll("_", " ")}</Td>
                <Td>{formatDateTime(order.placedAt)}</Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      {!isLoading && (data ?? []).length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title="No orders yet"
            hint="Orders will appear here once customers check out."
          />
        </div>
      ) : null}
      <Pagination page={page} onPageChange={setPage} rowCount={(data ?? []).length} limit={limit} />
    </div>
  );
}

const ORDER_TRANSITIONS: Record<string, string[]> = {
  pending_payment: ["confirmed", "cancelled"],
  confirmed: ["processing", "cancelled"],
  processing: ["completed", "cancelled"],
  completed: [],
  cancelled: [],
};

const REFUNDABLE_PAYMENT_STATUSES = new Set(["paid", "partially_refunded"]);

const refundSchema = z.object({
  amount: z.coerce.number().min(0.01, "Enter an amount greater than zero").optional(),
  reason: z.string().min(3, "A reason is required for the audit trail").max(300),
});

type RefundForm = z.infer<typeof refundSchema>;

function RefundModal({ order, onClose }: { order: AdminOrderDetail; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const remainingMinor = (order.payment?.amountMinor ?? 0) - (order.payment?.refundedMinor ?? 0);
  const form = useForm<RefundForm>({
    resolver: zodResolver(refundSchema),
    defaultValues: { amount: remainingMinor / 100, reason: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: RefundForm) =>
      api.refundOrder(order.id, {
        amountMinor: Math.round(values.amount! * 100),
        reason: values.reason,
      }),
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["order", order.id] }),
        queryClient.invalidateQueries({ queryKey: ["orders"] }),
      ]);
      toast.success(`Refunded ${formatMoney(result.refundedMinor, order.currencyCode)}.`);
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not issue the refund."),
  });

  return (
    <Modal title="Issue refund" onClose={onClose}>
      <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <p className="text-sm text-ink-muted">
          Up to {formatMoney(remainingMinor, order.currencyCode)} remains unrefunded on this{" "}
          {order.payment?.provider} payment.
        </p>
        <Field
          label={`Refund amount (${order.currencyCode})`}
          htmlFor="refund-amount"
          error={form.formState.errors.amount?.message}
        >
          <Input id="refund-amount" type="number" step="0.01" {...form.register("amount")} />
        </Field>
        <Field label="Reason" htmlFor="refund-reason" error={form.formState.errors.reason?.message}>
          <Textarea id="refund-reason" {...form.register("reason")} />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button type="submit" variant="destructive" disabled={mutation.isPending}>
            {mutation.isPending ? "Refunding..." : "Issue refund"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function OrderDetailPage() {
  const { id = "" } = useParams();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [refunding, setRefunding] = useState(false);
  const {
    data: order,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["order", id],
    queryFn: () => api.getOrder(id),
    retry: false,
  });

  const mutation = useMutation({
    mutationFn: (status: string) => api.updateOrderStatus(id, status),
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["order", id] }),
        queryClient.invalidateQueries({ queryKey: ["orders"] }),
      ]);
      toast.success(`Order moved to ${result.orderStatus.replaceAll("_", " ")}.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update the order."),
  });

  if (isLoading) return <p className="text-sm text-ink-muted">Loading order…</p>;
  if (isError || !order) return <EmptyState title="Order not found" />;

  const nextStates = ORDER_TRANSITIONS[order.orderStatus] ?? [];

  return (
    <div>
      <PageHeader
        title={order.publicReference}
        description={`${order.customerEmail} · placed ${formatDateTime(order.placedAt)}`}
        actions={<StatusPill status={order.orderStatus} />}
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <DataTableShell>
          <thead className="bg-canvas">
            <tr>
              <Th>Item</Th>
              <Th>SKU</Th>
              <Th>Qty</Th>
              <Th>Unit</Th>
              <Th>Line total</Th>
            </tr>
          </thead>
          <tbody>
            {order.items.length === 0 ? (
              <tr className="border-t border-line">
                <Td className="text-ink-muted">No line items recorded.</Td>
                <Td /> <Td /> <Td /> <Td />
              </tr>
            ) : (
              order.items.map((item) => (
                <tr key={item.id} className="border-t border-line">
                  <Td className="font-medium">
                    {item.productName}
                    <span className="block text-xs text-ink-muted">{item.variantName}</span>
                  </Td>
                  <Td>{item.sku}</Td>
                  <Td>{item.quantity}</Td>
                  <Td>{formatMoney(item.unitMinor, order.currencyCode)}</Td>
                  <Td className="font-medium">
                    {formatMoney(item.lineTotalMinor, order.currencyCode)}
                  </Td>
                </tr>
              ))
            )}
          </tbody>
        </DataTableShell>

        <aside className="h-fit space-y-4 rounded-md border border-line bg-surface p-4 shadow-card">
          <div>
            <h2 className="font-display text-lg text-ink">Summary</h2>
            <dl className="mt-3 space-y-1.5 text-sm">
              <Row label="Subtotal" value={formatMoney(order.subtotalMinor, order.currencyCode)} />
              <Row label="Delivery" value={formatMoney(order.deliveryMinor, order.currencyCode)} />
              <Row label="Discount" value={formatMoney(order.discountMinor, order.currencyCode)} />
              <Row label="Tax" value={formatMoney(order.taxMinor, order.currencyCode)} />
              <div className="flex justify-between border-t border-line pt-1.5 font-medium">
                <dt>Total</dt>
                <dd>{formatMoney(order.totalMinor, order.currencyCode)}</dd>
              </div>
            </dl>
          </div>
          <div className="space-y-1.5 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-ink-muted">Payment</span>
              <StatusPill status={order.paymentStatus} />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-ink-muted">Fulfilment</span>
              <StatusPill status={order.fulfilmentStatus} />
            </div>
          </div>
          <PermissionGate permission="orders.view">
            <div className="border-t border-line pt-3">
              <p className="mb-2 text-xs font-semibold tracking-wide text-ink-muted uppercase">
                Move order to
              </p>
              {nextStates.length === 0 ? (
                <p className="text-sm text-ink-muted">This order is in a final state.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {nextStates.map((status) => (
                    <Button
                      key={status}
                      variant={status === "cancelled" ? "destructive" : "primary"}
                      onClick={() => mutation.mutate(status)}
                      disabled={mutation.isPending}
                    >
                      {status.replaceAll("_", " ")}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          </PermissionGate>
          {order.payment &&
          order.payment.provider !== "cod" &&
          REFUNDABLE_PAYMENT_STATUSES.has(order.payment.status) &&
          order.payment.amountMinor > order.payment.refundedMinor ? (
            <PermissionGate permission="orders.refund">
              <div className="border-t border-line pt-3">
                <p className="mb-2 text-xs font-semibold tracking-wide text-ink-muted uppercase">
                  Payment
                </p>
                <p className="mb-2 text-sm text-ink-muted">
                  {formatMoney(order.payment.refundedMinor, order.currencyCode)} refunded of{" "}
                  {formatMoney(order.payment.amountMinor, order.currencyCode)} paid via{" "}
                  {order.payment.provider}.
                </p>
                <Button variant="destructive" onClick={() => setRefunding(true)}>
                  Issue refund
                </Button>
              </div>
            </PermissionGate>
          ) : null}
        </aside>
      </div>
      {refunding ? <RefundModal order={order} onClose={() => setRefunding(false)} /> : null}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-ink-muted">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Media
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function EditMediaModal({ asset, onClose }: { asset: AdminMediaAssetRow; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [altText, setAltText] = useState(asset.altText);
  const [caption, setCaption] = useState(asset.caption);

  const mutation = useMutation({
    mutationFn: () => api.updateMediaAsset(asset.id, { altText, caption }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-media"] });
      toast.success("Media details saved.");
      onClose();
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not save."),
  });

  return (
    <Modal title="Edit media" onClose={onClose}>
      <div className="space-y-4">
        <ImagePreview
          src={asset.url}
          alt={altText}
          label={asset.originalFilename}
          className="h-32 w-full"
        />
        <Field label="Alt text" htmlFor="media-alt">
          <Input
            id="media-alt"
            value={altText}
            onChange={(event) => setAltText(event.target.value)}
          />
        </Field>
        <Field label="Caption" htmlFor="media-caption">
          <Textarea
            id="media-caption"
            rows={2}
            value={caption}
            onChange={(event) => setCaption(event.target.value)}
          />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="primary"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export function MediaPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const limit = 6;
  const offset = (page - 1) * limit;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-media", page, searchQuery],
    queryFn: () => api.mediaLibrary({ limit, offset, search: searchQuery || undefined }),
  });

  const [editing, setEditing] = useState<AdminMediaAssetRow | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const assets = data ?? [];

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadImage(file),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-media"] });
      toast.success("Image uploaded.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not upload."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteMediaAsset(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-media"] });
      setDeletingId(null);
      toast.success("Image deleted.");
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : "Could not delete.");
      setDeletingId(null);
    },
  });

  return (
    <div>
      <PageHeader
        title="Media Library"
        description="Every uploaded image, with alt text and captions editable in place."
        actions={
          <PermissionGate permission="media.upload">
            <label>
              <Button
                variant="primary"
                type="button"
                disabled={uploadMutation.isPending}
                onClick={(event) =>
                  (event.currentTarget.nextElementSibling as HTMLInputElement)?.click()
                }
              >
                {uploadMutation.isPending ? "Uploading…" : "Upload image"}
              </Button>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                className="hidden"
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0];
                  if (file) uploadMutation.mutate(file);
                  event.currentTarget.value = "";
                }}
              />
            </label>
          </PermissionGate>
        }
      />
      {editing ? <EditMediaModal asset={editing} onClose={() => setEditing(null)} /> : null}
      {deletingId ? (
        <ConfirmDialog
          title="Delete image"
          description="This permanently removes the image from storage. Images still referenced by a product, page, article or recipe cannot be deleted."
          confirmLabel="Delete image"
          pendingLabel="Deleting…"
          isPending={deleteMutation.isPending}
          onCancel={() => setDeletingId(null)}
          onConfirm={() => deleteMutation.mutate(deletingId)}
        />
      ) : null}

      <div className="mb-6 flex gap-4">
        <div className="flex-1">
          <Input
            placeholder="Search images..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1); // Reset to page 1 on new search
            }}
          />
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-ink-muted">Loading media…</p>
      ) : assets.length === 0 ? (
        <EmptyState title="No media uploaded yet" hint="Upload an image to get started." />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {assets.map((asset) => (
            <li
              key={asset.id}
              className="overflow-hidden rounded-md border border-line bg-surface shadow-card"
            >
              <ImagePreview
                src={asset.url}
                alt={asset.altText}
                label={asset.originalFilename}
                className="h-36 w-full rounded-none"
              />
              <div className="px-3 py-2.5">
                <p className="truncate text-sm font-medium text-ink">{asset.originalFilename}</p>
                <p className="truncate text-xs text-ink-muted" title={asset.altText}>
                  alt: {asset.altText || "—"}
                </p>
                <p className="mt-1 text-xs text-ink-muted">
                  {formatBytes(asset.sizeBytes)}
                  {asset.widthPx && asset.heightPx ? ` · ${asset.widthPx} × ${asset.heightPx}` : ""}
                </p>
                <div className="mt-2 flex gap-2">
                  <PermissionGate permission="media.edit">
                    <Button variant="secondary" onClick={() => setEditing(asset)}>
                      Edit
                    </Button>
                  </PermissionGate>
                  <PermissionGate permission="media.delete">
                    <Button variant="destructive" onClick={() => setDeletingId(asset.id)}>
                      Delete
                    </Button>
                  </PermissionGate>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {assets.length > 0 || page > 1 ? (
        <div className="mt-8 flex justify-between border-t border-line pt-4">
          <Button
            variant="secondary"
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </Button>
          <span className="text-sm font-medium text-ink-muted">Page {page}</span>
          <Button
            variant="secondary"
            disabled={assets.length < limit}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Users & roles
// ---------------------------------------------------------------------------

const inviteSchema = z.object({
  email: z.string().email("Enter a valid email"),
  displayName: z.string().min(2, "Enter a name").max(120),
});

type InviteForm = z.infer<typeof inviteSchema>;

const userCreateSchema = inviteSchema.extend({
  password: z.string().min(10, "At least 10 characters").max(256),
});

type UserCreateForm = z.infer<typeof userCreateSchema>;

function RoleDropdown({
  id,
  roles,
  selected,
  onChange,
  label = "Roles",
  disabled = false,
}: {
  id: string;
  roles: AdminRole[];
  selected: string[];
  onChange: (roleIds: string[]) => void;
  label?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const selectedRoles = roles.filter((role) => selected.includes(role.id));
  const summary =
    selectedRoles.length > 0 ? selectedRoles.map((role) => role.name).join(", ") : "Select roles";

  function toggleRole(roleId: string) {
    onChange(
      selected.includes(roleId) ? selected.filter((id) => id !== roleId) : [...selected, roleId],
    );
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        id={id}
        type="button"
        className="flex min-h-9 w-full items-center justify-between gap-3 rounded-sm border border-line-strong bg-surface px-3 text-left text-sm text-ink disabled:cursor-not-allowed disabled:opacity-50"
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
      >
        <span className="min-w-0 truncate">{summary}</span>
        <span aria-hidden className="text-xs text-ink-muted">
          {open ? "^" : "v"}
        </span>
      </button>
      {open ? (
        <div
          role="listbox"
          aria-multiselectable="true"
          aria-label={label}
          className="absolute z-[110] mt-1 max-h-56 w-full overflow-y-auto rounded-sm border border-line bg-surface p-1.5 shadow-overlay"
        >
          {roles.length === 0 ? (
            <p className="px-2 py-2 text-sm text-ink-muted">No roles available.</p>
          ) : (
            roles.map((role) => {
              const isSelected = selected.includes(role.id);

              return (
                <button
                  key={role.id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className="flex w-full items-start justify-between gap-3 rounded-sm px-2 py-2 text-left text-sm hover:bg-subtle/60"
                  onClick={() => toggleRole(role.id)}
                >
                  <span className="min-w-0">
                    <span className="block font-medium text-ink">{role.name}</span>
                    <span className="block text-xs leading-5 text-ink-muted">
                      {role.description}
                    </span>
                  </span>
                  <span
                    className={
                      isSelected
                        ? "shrink-0 rounded-sm bg-brand px-2 py-0.5 text-xs font-medium text-ink-inverse"
                        : "shrink-0 rounded-sm border border-line px-2 py-0.5 text-xs font-medium text-ink-muted"
                    }
                  >
                    {isSelected ? "Selected" : "Add"}
                  </span>
                </button>
              );
            })
          )}
        </div>
      ) : null}
    </div>
  );
}

function InviteUserModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const roles = useQuery({ queryKey: ["roles"], queryFn: api.roles });
  const assignableRoles = (roles.data ?? []).filter((role) => role.key !== "farm_owner");
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const form = useForm<InviteForm>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: "", displayName: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: InviteForm) =>
      api.inviteUser({
        email: values.email,
        displayName: values.displayName,
        roleIds: selectedRoles,
      }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      if (result.emailSent) {
        toast.success("Invitation email sent.");
      } else {
        toast.error(
          "User invited, but the invitation email could not be delivered. Share a password reset link with them manually.",
        );
      }
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not invite the user."),
  });

  return (
    <Modal title="Invite user" onClose={onClose}>
      <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Email" htmlFor="invite-email" error={form.formState.errors.email?.message}>
          <Input id="invite-email" type="email" {...form.register("email")} />
        </Field>
        <Field
          label="Name"
          htmlFor="invite-name"
          error={form.formState.errors.displayName?.message}
        >
          <Input id="invite-name" {...form.register("displayName")} />
        </Field>
        <Field label="Roles" htmlFor="invite-roles">
          <RoleDropdown
            id="invite-roles"
            roles={assignableRoles}
            selected={selectedRoles}
            onChange={setSelectedRoles}
            label="Invite user roles"
            disabled={roles.isLoading}
          />
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Inviting…" : "Send invite"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function AddUserModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const roles = useQuery({ queryKey: ["roles"], queryFn: api.roles });
  const assignableRoles = (roles.data ?? []).filter((role) => role.key !== "farm_owner");
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const form = useForm<UserCreateForm>({
    resolver: zodResolver(userCreateSchema),
    defaultValues: { email: "", displayName: "", password: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: UserCreateForm) =>
      api.createUser({
        email: values.email,
        displayName: values.displayName,
        password: values.password,
        roleIds: selectedRoles,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("User created. They can sign in with the password you set.");
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not add the user."),
  });

  return (
    <Modal title="Add user" onClose={onClose}>
      <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Email" htmlFor="add-user-email" error={form.formState.errors.email?.message}>
          <Input id="add-user-email" type="email" {...form.register("email")} />
        </Field>
        <Field
          label="Name"
          htmlFor="add-user-name"
          error={form.formState.errors.displayName?.message}
        >
          <Input id="add-user-name" {...form.register("displayName")} />
        </Field>
        <Field
          label="Temporary password"
          htmlFor="add-user-password"
          error={form.formState.errors.password?.message}
        >
          <Input id="add-user-password" type="text" {...form.register("password")} />
        </Field>
        <Field label="Roles" htmlFor="add-user-roles">
          <RoleDropdown
            id="add-user-roles"
            roles={assignableRoles}
            selected={selectedRoles}
            onChange={setSelectedRoles}
            label="New user roles"
            disabled={roles.isLoading}
          />
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating..." : "Add user"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function EditRolesModal({ user, onClose }: { user: AdminUserRow; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const roles = useQuery({ queryKey: ["roles"], queryFn: api.roles });
  const [selected, setSelected] = useState<string[]>(user.roleIds ?? []);

  const mutation = useMutation({
    mutationFn: () => api.setUserRoles(user.id, selected),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Roles updated.");
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update roles."),
  });

  return (
    <Modal title={`Roles — ${user.displayName}`} onClose={onClose}>
      <Field label="Assigned roles" htmlFor="edit-user-roles">
        <RoleDropdown
          id="edit-user-roles"
          roles={roles.data ?? []}
          selected={selected}
          onChange={setSelected}
          label={`Roles for ${user.displayName}`}
          disabled={roles.isLoading}
        />
      </Field>
      <div className="mt-4 flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button
          type="button"
          variant="primary"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? "Saving…" : "Save roles"}
        </Button>
      </div>
    </Modal>
  );
}

function ResetUserPasswordModal({ user, onClose }: { user: AdminUserRow; onClose: () => void }) {
  const toast = useToast();
  const [result, setResult] = useState<{ email: string } | null>(null);

  const mutation = useMutation({
    mutationFn: () => api.sendUserPasswordReset(user.id),
    onSuccess: (response) => {
      setResult(response);
      if (response.emailSent) {
        toast.success("Password reset email sent.");
      } else {
        toast.error(
          "Reset link created, but the email could not be delivered. Share the link with them manually.",
        );
      }
    },
    onError: (error) =>
      toast.error(
        error instanceof ApiError ? error.message : "Could not send the password reset email.",
      ),
  });

  return (
    <Modal title={`Password - ${user.displayName}`} onClose={onClose}>
      {result ? (
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">
            A password reset link has been sent to {result.email}. They can use it to set a new
            password.
          </p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="primary" onClick={onClose}>
              Done
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-ink-muted">
            Send a secure password reset link to this user. They will set their new password from
            the admin reset page.
          </p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? "Sending..." : "Send reset email"}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

const farmOwnerSchema = z.object({
  email: z.string().email("Enter a valid email"),
  displayName: z.string().min(2, "Enter a name").max(120),
  farmId: z.string().min(1, "Pick a farm"),
  password: z.string().min(10, "At least 10 characters").max(256),
});

type FarmOwnerForm = z.infer<typeof farmOwnerSchema>;

function AddFarmOwnerModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const farms = useQuery({ queryKey: ["farms"], queryFn: () => api.farms({ limit: 100 }) });
  const form = useForm<FarmOwnerForm>({
    resolver: zodResolver(farmOwnerSchema),
    defaultValues: { email: "", displayName: "", farmId: "", password: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: FarmOwnerForm) => api.createFarmOwner(values),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Farm owner created. They can sign in with the password you set.");
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not create the farm owner."),
  });

  return (
    <Modal title="Add farm owner" onClose={onClose}>
      <p className="mb-4 text-sm text-ink-muted">
        A farm owner is a sub-admin who can only manage their own farm&apos;s products and stock.
      </p>
      <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Farm" htmlFor="fo-farm" error={form.formState.errors.farmId?.message}>
          <Select id="fo-farm" {...form.register("farmId")}>
            <option value="">Select a farm…</option>
            {(farms.data ?? []).map((farm) => (
              <option key={farm.id} value={farm.id}>
                {farm.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Name" htmlFor="fo-name" error={form.formState.errors.displayName?.message}>
          <Input id="fo-name" {...form.register("displayName")} />
        </Field>
        <Field label="Email" htmlFor="fo-email" error={form.formState.errors.email?.message}>
          <Input id="fo-email" type="email" {...form.register("email")} />
        </Field>
        <Field
          label="Temporary password"
          htmlFor="fo-password"
          error={form.formState.errors.password?.message}
        >
          <Input id="fo-password" type="text" {...form.register("password")} />
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating…" : "Create farm owner"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function UsersPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const limit = 25;
  const offset = (page - 1) * limit;
  const { data, isLoading, isError } = useQuery({
    queryKey: ["users", page, searchQuery],
    queryFn: () => api.users({ limit, offset, search: searchQuery || undefined }),
  });
  const roles = useQuery({ queryKey: ["roles"], queryFn: api.roles });
  const [inviting, setInviting] = useState(false);
  const [addingUser, setAddingUser] = useState(false);
  const [addingOwner, setAddingOwner] = useState(false);
  const [editingRoles, setEditingRoles] = useState<AdminUserRow | null>(null);
  const [resettingPassword, setResettingPassword] = useState<AdminUserRow | null>(null);
  const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
  const [confirmingDelete, setConfirmingDelete] = useState<AdminUserRow[] | null>(null);
  const [managingRoles, setManagingRoles] = useState(false);

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => api.setUserStatus(id, status),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("User status updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update status."),
  });

  const roleMutation = useMutation({
    mutationFn: ({ id, roleId }: { id: string; roleId: string }) =>
      api.setUserRoles(id, roleId ? [roleId] : []),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("User role updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update role."),
  });

  const deleteMutation = useMutation({
    mutationFn: (userIds: string[]) => api.deleteUsers(userIds),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      setSelectedUserIds([]);
      setConfirmingDelete(null);
      toast.success(`${result.count} user${result.count === 1 ? "" : "s"} deleted.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete users."),
  });

  const users = data ?? [];
  const isOwnerRole = (user: AdminUserRow) =>
    user.roles.some((role) => role.toLowerCase().includes("super administrator"));
  const deletableUsers = users.filter((user) => !isOwnerRole(user));
  const selectedUsers = deletableUsers.filter((user) => selectedUserIds.includes(user.id));
  const allSelected = deletableUsers.length > 0 && selectedUserIds.length === deletableUsers.length;

  function toggleUser(userId: string) {
    setSelectedUserIds((current) =>
      current.includes(userId) ? current.filter((id) => id !== userId) : [...current, userId],
    );
  }

  function toggleAllUsers() {
    setSelectedUserIds(allSelected ? [] : deletableUsers.map((user) => user.id));
  }

  return (
    <div>
      <PageHeader
        title="Users & Roles"
        description="Roles are collections of permissions; the API checks permissions, never role names."
        actions={
          <div className="flex gap-2">
            <PermissionGate permission="users.manage_roles">
              <Button variant="secondary" onClick={() => setManagingRoles(true)}>
                Add / edit roles
              </Button>
            </PermissionGate>
            <PermissionGate permission="users.invite">
              <div className="flex gap-2">
                {selectedUserIds.length > 0 ? (
                  <Button
                    variant="destructive"
                    onClick={() => setConfirmingDelete(selectedUsers)}
                    disabled={deleteMutation.isPending}
                  >
                    Delete selected ({selectedUserIds.length})
                  </Button>
                ) : null}
                <Button variant="secondary" onClick={() => setAddingOwner(true)}>
                  Add farm owner
                </Button>
                <Button variant="secondary" onClick={() => setAddingUser(true)}>
                  Add user
                </Button>
                <Button variant="primary" onClick={() => setInviting(true)}>
                  Invite user
                </Button>
              </div>
            </PermissionGate>
          </div>
        }
      />
      {managingRoles ? <ManageRolesModal onClose={() => setManagingRoles(false)} /> : null}
      {inviting ? <InviteUserModal onClose={() => setInviting(false)} /> : null}
      {addingUser ? <AddUserModal onClose={() => setAddingUser(false)} /> : null}
      {addingOwner ? <AddFarmOwnerModal onClose={() => setAddingOwner(false)} /> : null}
      {editingRoles ? (
        <EditRolesModal user={editingRoles} onClose={() => setEditingRoles(null)} />
      ) : null}
      {resettingPassword ? (
        <ResetUserPasswordModal
          user={resettingPassword}
          onClose={() => setResettingPassword(null)}
        />
      ) : null}
      {confirmingDelete ? (
        <ConfirmDialog
          title={
            confirmingDelete.length === 1
              ? "Delete user"
              : `Delete ${confirmingDelete.length} users`
          }
          description={
            confirmingDelete.length === 1
              ? `${confirmingDelete.at(0)?.displayName ?? "This user"} will be removed from the users list and signed out.`
              : "Selected users will be removed from the users list and signed out."
          }
          confirmLabel={confirmingDelete.length === 1 ? "Delete user" : "Delete users"}
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmingDelete(null)}
          onConfirm={() => deleteMutation.mutate(confirmingDelete.map((user) => user.id))}
        />
      ) : null}

      {isError ? (
        <EmptyState
          title="Users unavailable"
          hint="Check that this account has users.view permission and that the API is connected."
        />
      ) : null}

      {!isError ? (
        <div className="mb-4 max-w-sm">
          <SearchBox
            value={searchQuery}
            onSearch={(value) => {
              setSearchQuery(value);
              setPage(1);
            }}
            placeholder="Search by name or email..."
            aria-label="Search users"
          />
        </div>
      ) : null}

      {!isError ? (
        <DataTableShell>
          <thead className="bg-canvas">
            <tr>
              <Th>
                <input
                  type="checkbox"
                  aria-label="Select all users"
                  checked={allSelected}
                  onChange={toggleAllUsers}
                />
              </Th>
              <Th>Name</Th>
              <Th>Email</Th>
              <Th>Status</Th>
              <Th>Roles</Th>
              <Th>Last sign-in</Th>
              <Th>Actions</Th>
            </tr>
          </thead>
          {isLoading ? (
            <LoadingRows columns={7} />
          ) : (
            <tbody>
              {users.length === 0 ? (
                <tr className="border-t border-line">
                  <Td colSpan={7}>
                    <EmptyState
                      title="No users found"
                      hint="Invite a user or add a farm owner to populate this page."
                    />
                  </Td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id} className="border-t border-line">
                    <Td>
                      <input
                        type="checkbox"
                        aria-label={`Select ${user.displayName}`}
                        checked={selectedUserIds.includes(user.id)}
                        onChange={() => toggleUser(user.id)}
                      />
                    </Td>
                    <Td className="font-medium">{user.displayName}</Td>
                    <Td className="text-ink-muted">{user.email}</Td>
                    <Td>
                      <StatusPill status={user.status} />
                    </Td>
                    <Td>{user.roles.join(", ") || "—"}</Td>
                    <Td>{user.lastSignInAt ? formatDateTime(user.lastSignInAt) : "Never"}</Td>
                    <Td>
                      <PermissionGate
                        permission="users.manage_roles"
                        fallback={<span className="text-xs text-ink-muted">—</span>}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <Select
                            aria-label={`Role for ${user.displayName}`}
                            value={user.roleIds?.[0] ?? ""}
                            disabled={roles.isLoading || roleMutation.isPending}
                            onChange={(event) =>
                              roleMutation.mutate({ id: user.id, roleId: event.target.value })
                            }
                            className="min-w-44"
                          >
                            <option value="">No role</option>
                            {(roles.data ?? []).map((role) => (
                              <option key={role.id} value={role.id}>
                                {role.name}
                              </option>
                            ))}
                          </Select>
                          <button
                            type="button"
                            className="text-sm text-brand underline-offset-4 hover:underline"
                            onClick={() => setEditingRoles(user)}
                          >
                            Roles
                          </button>
                          <button
                            type="button"
                            className="text-sm text-ink-muted underline-offset-4 hover:text-danger hover:underline"
                            onClick={() => setConfirmingDelete([user])}
                            disabled={deleteMutation.isPending}
                          >
                            Delete
                          </button>
                          <button
                            type="button"
                            className="text-sm text-ink-muted underline-offset-4 hover:text-danger hover:underline"
                            onClick={() =>
                              statusMutation.mutate({
                                id: user.id,
                                status: user.status === "disabled" ? "active" : "disabled",
                              })
                            }
                            disabled={statusMutation.isPending}
                          >
                            {user.status === "disabled" ? "Enable" : "Disable"}
                          </button>
                          <button
                            type="button"
                            className="text-sm text-ink-muted underline-offset-4 hover:text-brand hover:underline"
                            onClick={() => setResettingPassword(user)}
                          >
                            Password
                          </button>
                        </div>
                      </PermissionGate>
                    </Td>
                  </tr>
                ))
              )}
            </tbody>
          )}
        </DataTableShell>
      ) : null}
      {!isError ? (
        <Pagination page={page} onPageChange={setPage} rowCount={users.length} limit={limit} />
      ) : null}

      <section className="mt-8 space-y-3 border-t border-line pt-5">
        <div>
          <h2 className="font-display text-lg text-ink">Role catalogue</h2>
          <p className="text-sm text-ink-muted">
            These roles define the permission sets available when inviting or editing users.
          </p>
        </div>
        {roles.isLoading ? (
          <p className="text-sm text-ink-muted">Loading roles...</p>
        ) : roles.isError ? (
          <EmptyState
            title="Roles unavailable"
            hint="The role list could not be loaded from the API."
          />
        ) : (roles.data ?? []).length === 0 ? (
          <EmptyState title="No roles available" hint="Roles have not been seeded yet." />
        ) : (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {(roles.data ?? []).map((role) => (
              <div key={role.id} className="rounded-md border border-line bg-surface p-4">
                <p className="font-medium text-ink">{role.name}</p>
                <p className="mt-1 text-xs text-ink-muted">{role.key}</p>
                {role.description ? (
                  <p className="mt-2 text-sm leading-6 text-ink-muted">{role.description}</p>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Contact attempts
// ---------------------------------------------------------------------------

function ContactMessageCard({ message }: { message: AdminContactMessageRow }) {
  return (
    <article className="rounded-md border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-lg text-ink">{message.subject}</h2>
          <p className="mt-1 text-sm text-ink-muted">
            {message.name} ·{" "}
            <a href={`mailto:${message.email}`} className="text-brand hover:underline">
              {message.email}
            </a>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusPill status={message.status} />
          <span className="text-xs text-ink-muted">{formatDateTime(message.createdAt)}</span>
        </div>
      </div>
      <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-ink">{message.message}</p>
    </article>
  );
}

export function ContactAttemptsPage() {
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const limit = 25;
  const offset = (page - 1) * limit;
  const { data, isLoading, isError } = useQuery({
    queryKey: ["contact-messages", page, searchQuery],
    queryFn: () => api.contactMessages({ limit, offset, search: searchQuery || undefined }),
  });
  const messages = data ?? [];

  return (
    <div>
      <PageHeader
        title="Contact Attempts"
        description="Messages submitted from the storefront Contact us page."
      />

      {isError ? (
        <EmptyState
          title="Contact attempts unavailable"
          hint="Only main admins can view customer contact messages."
        />
      ) : null}

      {!isError ? (
        <div className="mb-4 max-w-sm">
          <SearchBox
            value={searchQuery}
            onSearch={(value) => {
              setSearchQuery(value);
              setPage(1);
            }}
            placeholder="Search by name, email or subject..."
            aria-label="Search contact attempts"
          />
        </div>
      ) : null}

      {!isError ? (
        <div className="space-y-3">
          {isLoading ? (
            <DataTableShell>
              <LoadingRows columns={3} />
            </DataTableShell>
          ) : messages.length === 0 ? (
            <EmptyState
              title="No contact attempts"
              hint="Messages sent from the storefront contact page will appear here."
            />
          ) : (
            messages.map((message) => <ContactMessageCard key={message.id} message={message} />)
          )}
        </div>
      ) : null}
      {!isError ? (
        <Pagination page={page} onPageChange={setPage} rowCount={messages.length} limit={limit} />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Audit log
// ---------------------------------------------------------------------------

export function AuditPage() {
  const [page, setPage] = useState(1);
  const limit = 25;
  const offset = (page - 1) * limit;
  const { data, isLoading } = useQuery({
    queryKey: ["audit", page],
    queryFn: () => api.audit({ limit, offset }),
  });
  const rows = data ?? [];

  return (
    <div>
      <PageHeader
        title="Audit Log"
        description="Append-only. Actor, action, entity, and request id for every sensitive operation."
      />
      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Actor</Th>
            <Th>Action</Th>
            <Th>Entity</Th>
            <Th>Request ID</Th>
            <Th>Time</Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={5} />
        ) : (
          <tbody>
            {rows.map((entry) => (
              <tr key={entry.id} className="border-t border-line">
                <Td className="font-medium">{entry.actorName}</Td>
                <Td>{entry.action}</Td>
                <Td className="text-ink-muted">
                  {entry.entityType} · {entry.entityId}
                </Td>
                <Td className="font-mono text-xs text-ink-muted">{entry.requestId}</Td>
                <Td>{formatDateTime(entry.createdAt)}</Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      <Pagination page={page} onPageChange={setPage} rowCount={rows.length} limit={limit} />
    </div>
  );
}
