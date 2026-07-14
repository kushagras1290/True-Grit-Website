/** Inventory (persisted adjustments), orders (with detail + status transitions),
 * users & roles (invite, enable/disable, role assignment), media, audit log. */

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AdminUserRow } from "@truegrit/contracts";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router";
import { z } from "zod";

import {
  Button,
  DataTableShell,
  EmptyState,
  Field,
  Input,
  LoadingRows,
  Modal,
  PageHeader,
  Select,
  StatusPill,
  Td,
  Textarea,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import { formatDateTime, formatMoney } from "../lib/format";
import { PermissionGate } from "../lib/permissions";

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

export function InventoryPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["inventory"], queryFn: api.inventory });

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

  return (
    <div>
      <PageHeader
        title="Inventory"
        description="Available is always derived (on hand − reserved). Every change is a movement."
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <DataTableShell>
          <thead className="bg-canvas">
            <tr>
              <Th>Product</Th>
              <Th>Variant</Th>
              <Th>SKU</Th>
              <Th>On hand</Th>
              <Th>Reserved</Th>
              <Th>Available</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          {isLoading ? (
            <LoadingRows columns={7} />
          ) : (
            <tbody>
              {(data ?? []).map((row) => {
                const available = row.onHand - row.reserved;
                const status =
                  available <= 0
                    ? "out_of_stock"
                    : available <= row.reorderThreshold
                      ? "low_stock"
                      : "in_stock";
                return (
                  <tr key={row.variantId} className="border-t border-line">
                    <Td className="font-medium">{row.productName}</Td>
                    <Td className="text-ink-muted">{row.variantName}</Td>
                    <Td>{row.sku}</Td>
                    <Td>{row.onHand}</Td>
                    <Td>{row.reserved}</Td>
                    <Td className="font-medium">{available}</Td>
                    <Td>
                      <StatusPill status={status} />
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          )}
        </DataTableShell>

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
// Orders
// ---------------------------------------------------------------------------

export function OrdersPage() {
  const { data, isLoading } = useQuery({ queryKey: ["orders"], queryFn: api.orders });

  return (
    <div>
      <PageHeader
        title="Orders"
        description="Snapshots at purchase time — catalogue edits never rewrite an order."
      />
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

export function OrderDetailPage() {
  const { id = "" } = useParams();
  const toast = useToast();
  const queryClient = useQueryClient();
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
        </aside>
      </div>
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

const DEMO_MEDIA = [
  {
    id: "med_hero_home",
    name: "harvest-table.jpg",
    alt: "A wooden harvest table with seasonal organic produce",
    size: "482 KB",
    dims: "2400 × 1500",
  },
  {
    id: "med_farm_devika",
    name: "devika-fields.jpg",
    alt: "Morning light over the terraced fields of Devika Organics",
    size: "391 KB",
    dims: "2000 × 1250",
  },
  {
    id: "med_prod_mango",
    name: "alphonso-crate.jpg",
    alt: "A crate of ripe Alphonso mangoes",
    size: "287 KB",
    dims: "1600 × 1600",
  },
];

export function MediaPage() {
  return (
    <div>
      <PageHeader
        title="Media Library"
        description="Uploads go through presigned R2 URLs, are checksummed, and quarantine on failed validation."
        actions={
          <PermissionGate permission="media.upload">
            <Button variant="primary" title="Uploads require the R2 storage binding" disabled>
              Upload (needs R2)
            </Button>
          </PermissionGate>
        }
      />
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {DEMO_MEDIA.map((asset) => (
          <li
            key={asset.id}
            className="overflow-hidden rounded-md border border-line bg-surface shadow-card"
          >
            <div
              role="img"
              aria-label={asset.alt}
              className="flex h-36 items-end bg-gradient-to-br from-subtle to-canvas p-3"
            >
              <span className="rounded-sm bg-surface/90 px-2 py-0.5 text-xs text-ink-muted">
                {asset.dims}
              </span>
            </div>
            <div className="px-3 py-2.5">
              <p className="truncate text-sm font-medium text-ink">{asset.name}</p>
              <p className="truncate text-xs text-ink-muted" title={asset.alt}>
                alt: {asset.alt}
              </p>
              <p className="mt-1 text-xs text-ink-muted">{asset.size} · ready</p>
            </div>
          </li>
        ))}
      </ul>
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

function InviteUserModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const roles = useQuery({ queryKey: ["roles"], queryFn: api.roles });
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
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Invitation created.");
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not invite the user."),
  });

  function toggleRole(roleId: string) {
    setSelectedRoles((current) =>
      current.includes(roleId) ? current.filter((id) => id !== roleId) : [...current, roleId],
    );
  }

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
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-ink">Roles</legend>
          <div className="grid max-h-44 gap-1.5 overflow-y-auto rounded-sm border border-line p-2">
            {(roles.data ?? []).map((role) => (
              <label key={role.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selectedRoles.includes(role.id)}
                  onChange={() => toggleRole(role.id)}
                />
                <span>{role.name}</span>
                <span className="text-xs text-ink-muted">{role.description}</span>
              </label>
            ))}
          </div>
        </fieldset>
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

  function toggle(roleId: string) {
    setSelected((current) =>
      current.includes(roleId) ? current.filter((id) => id !== roleId) : [...current, roleId],
    );
  }

  return (
    <Modal title={`Roles — ${user.displayName}`} onClose={onClose}>
      <div className="grid max-h-64 gap-1.5 overflow-y-auto rounded-sm border border-line p-2">
        {(roles.data ?? []).map((role) => (
          <label key={role.id} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selected.includes(role.id)}
              onChange={() => toggle(role.id)}
            />
            <span>{role.name}</span>
            <span className="text-xs text-ink-muted">{role.description}</span>
          </label>
        ))}
      </div>
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
  const farms = useQuery({ queryKey: ["farms"], queryFn: api.farms });
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
  const { data, isLoading } = useQuery({ queryKey: ["users"], queryFn: api.users });
  const [inviting, setInviting] = useState(false);
  const [addingOwner, setAddingOwner] = useState(false);
  const [editingRoles, setEditingRoles] = useState<AdminUserRow | null>(null);

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => api.setUserStatus(id, status),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("User status updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update status."),
  });

  return (
    <div>
      <PageHeader
        title="Users & Roles"
        description="Roles are collections of permissions; the API checks permissions, never role names."
        actions={
          <PermissionGate permission="users.invite">
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setAddingOwner(true)}>
                Add farm owner
              </Button>
              <Button variant="primary" onClick={() => setInviting(true)}>
                Invite user
              </Button>
            </div>
          </PermissionGate>
        }
      />
      {inviting ? <InviteUserModal onClose={() => setInviting(false)} /> : null}
      {addingOwner ? <AddFarmOwnerModal onClose={() => setAddingOwner(false)} /> : null}
      {editingRoles ? (
        <EditRolesModal user={editingRoles} onClose={() => setEditingRoles(null)} />
      ) : null}

      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Name</Th>
            <Th>Email</Th>
            <Th>Status</Th>
            <Th>Roles</Th>
            <Th>Last sign-in</Th>
            <Th>Actions</Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={6} />
        ) : (
          <tbody>
            {(data ?? []).map((user) => (
              <tr key={user.id} className="border-t border-line">
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
                    <div className="flex gap-2">
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
                    </div>
                  </PermissionGate>
                </Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Audit log
// ---------------------------------------------------------------------------

export function AuditPage() {
  const { data, isLoading } = useQuery({ queryKey: ["audit"], queryFn: api.audit });

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
            {(data ?? []).map((entry) => (
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
    </div>
  );
}
