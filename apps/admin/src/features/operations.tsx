/** Inventory (with auditable adjustment form), orders, media, users, audit log. */

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  Button,
  DataTableShell,
  EmptyState,
  Field,
  Input,
  LoadingRows,
  PageHeader,
  StatusPill,
  Td,
  Th,
} from "../components/ui";
import { api } from "../lib/api";
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
  const { data, isLoading } = useQuery({ queryKey: ["inventory"], queryFn: api.inventory });
  const [lastAdjustment, setLastAdjustment] = useState<string | null>(null);

  const form = useForm<AdjustmentForm>({
    resolver: zodResolver(adjustmentSchema),
    defaultValues: { sku: "", quantityDelta: 0, reasonCode: "manual_adjustment", note: "" },
  });

  return (
    <div>
      <PageHeader
        title="Inventory"
        description="Available is always derived (on hand − reserved). Every change is a movement."
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
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
                      : "active";
                return (
                  <tr key={row.variantId} className="border-t border-line">
                    <Td className="font-medium">{row.productName}</Td>
                    <Td className="text-ink-muted">{row.variantName}</Td>
                    <Td>{row.sku}</Td>
                    <Td>{row.onHand}</Td>
                    <Td>{row.reserved}</Td>
                    <Td className="font-medium">{available}</Td>
                    <Td>
                      <StatusPill status={status === "active" ? "in_stock" : status} />
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
            onSubmit={form.handleSubmit((values) => {
              setLastAdjustment(
                `${values.quantityDelta > 0 ? "+" : ""}${values.quantityDelta} recorded for ${values.sku} (${values.reasonCode})`,
              );
              form.reset();
            })}
          >
            <h2 className="font-display text-lg text-ink">Record adjustment</h2>
            <Field label="SKU" htmlFor="sku" error={form.formState.errors.sku?.message}>
              <Input id="sku" placeholder="TRG-RJM-500" {...form.register("sku")} />
            </Field>
            <Field
              label="Quantity delta"
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
              <select
                id="reasonCode"
                className="min-h-9 w-full rounded-sm border border-line-strong bg-surface px-3 text-sm"
                {...form.register("reasonCode")}
              >
                <option value="receipt">Receipt</option>
                <option value="manual_adjustment">Manual adjustment</option>
                <option value="write_off">Write off</option>
                <option value="correction">Correction</option>
              </select>
            </Field>
            <Field
              label="Note (required)"
              htmlFor="note"
              error={form.formState.errors.note?.message}
            >
              <Input id="note" placeholder="Why is stock changing?" {...form.register("note")} />
            </Field>
            <Button type="submit" variant="primary" className="w-full">
              Record movement
            </Button>
            <p role="status" className="text-xs text-success">
              {lastAdjustment ?? ""}
            </p>
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
              <tr key={order.id} className="border-t border-line">
                <Td className="font-medium">{order.publicReference}</Td>
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
            <Button variant="primary">Upload</Button>
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

export function UsersPage() {
  const { data, isLoading } = useQuery({ queryKey: ["users"], queryFn: api.users });

  return (
    <div>
      <PageHeader
        title="Users & Roles"
        description="Roles are collections of permissions; the API checks permissions, never role names."
        actions={
          <PermissionGate permission="users.invite">
            <Button variant="primary">Invite user</Button>
          </PermissionGate>
        }
      />
      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Name</Th>
            <Th>Email</Th>
            <Th>Status</Th>
            <Th>Roles</Th>
            <Th>Last sign-in</Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={5} />
        ) : (
          <tbody>
            {(data ?? []).map((user) => (
              <tr key={user.id} className="border-t border-line">
                <Td className="font-medium">{user.displayName}</Td>
                <Td className="text-ink-muted">{user.email}</Td>
                <Td>
                  <StatusPill status={user.status} />
                </Td>
                <Td>{user.roles.join(", ")}</Td>
                <Td>{user.lastSignInAt ? formatDateTime(user.lastSignInAt) : "Never"}</Td>
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
