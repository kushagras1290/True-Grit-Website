/** Coupons and promotions (migration 0005, extended by 0060).
 *
 * A promotion with no coupons is automatic -- it applies to every eligible
 * cart with no code. One or more coupons make it code-gated. The sitewide
 * on/off switch lives on Site Settings, next to the other storefront
 * switches -- this page only manages the campaigns and codes themselves. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  Button,
  ConfirmDialog,
  DataTableShell,
  EmptyState,
  Field,
  Input,
  LoadingRows,
  Modal,
  Pagination,
  SearchBox,
  Select,
  StatusPill,
  Td,
  Textarea,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import { formatDateTime, formatMoney } from "../lib/format";
import { usePermissions } from "../lib/permissions";
import { T } from "../lib/i18n";

const STATUS_OPTIONS = ["draft", "scheduled", "active", "paused", "ended", "archived"];
const ACTION_LABELS: Record<string, string> = {
  percentage_discount: "Percentage off",
  fixed_discount: "Fixed amount off",
  free_delivery: "Free delivery",
};

interface PromotionFormState {
  name: string;
  headline: string;
  description: string;
  status: string;
  priority: string;
  startsAt: string;
  endsAt: string;
  stackingPolicy: string;
  usageLimitTotal: string;
  usageLimitPerCustomer: string;
  minSubtotal: string;
  actionType: string;
  percentOff: string;
  maximumDiscount: string;
  amountOff: string;
}

const EMPTY_FORM: PromotionFormState = {
  name: "",
  headline: "",
  description: "",
  status: "draft",
  priority: "0",
  startsAt: "",
  endsAt: "",
  stackingPolicy: "exclusive",
  usageLimitTotal: "",
  usageLimitPerCustomer: "",
  minSubtotal: "",
  actionType: "percentage_discount",
  percentOff: "10",
  maximumDiscount: "",
  amountOff: "",
};

function toIsoOrNull(dateOnly: string): string | null {
  return dateOnly ? `${dateOnly}T00:00:00Z` : null;
}

function toMinorOrNull(rupees: string): number | null {
  const trimmed = rupees.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? Math.round(parsed * 100) : null;
}

function CreatePromotionModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState<PromotionFormState>(EMPTY_FORM);

  function update<K extends keyof PromotionFormState>(key: K, value: PromotionFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  const mutation = useMutation({
    mutationFn: () =>
      api.createPromotion({
        name: form.name.trim(),
        headline: form.headline.trim() || null,
        description: form.description.trim() || null,
        status: form.status,
        priority: Number(form.priority) || 0,
        startsAt: toIsoOrNull(form.startsAt),
        endsAt: toIsoOrNull(form.endsAt),
        stackingPolicy: form.stackingPolicy,
        usageLimitTotal: form.usageLimitTotal ? Number(form.usageLimitTotal) : null,
        usageLimitPerCustomer: form.usageLimitPerCustomer
          ? Number(form.usageLimitPerCustomer)
          : null,
        minSubtotalMinor: toMinorOrNull(form.minSubtotal),
        actionType: form.actionType,
        valueBasisPoints:
          form.actionType === "percentage_discount"
            ? Math.round((Number(form.percentOff) || 0) * 100)
            : null,
        amountMinor: form.actionType === "fixed_discount" ? toMinorOrNull(form.amountOff) : null,
        maximumDiscountMinor:
          form.actionType === "percentage_discount" ? toMinorOrNull(form.maximumDiscount) : null,
      }),
    onSuccess: () => {
      toast.success("Promotion created.");
      onCreated();
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not create the promotion."),
  });

  return (
    <Modal title="New promotion" onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (!form.name.trim()) {
            toast.error("Give the promotion a name.");
            return;
          }
          if (form.actionType === "percentage_discount" && !form.percentOff) {
            toast.error("Set a percentage.");
            return;
          }
          if (form.actionType === "fixed_discount" && !form.amountOff) {
            toast.error("Set an amount.");
            return;
          }
          mutation.mutate();
        }}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Internal name" htmlFor="promo-name">
            <Input
              id="promo-name"
              value={form.name}
              maxLength={160}
              onChange={(event) => update("name", event.target.value)}
              placeholder="Diwali 2026"
            />
          </Field>
          <Field label="Status" htmlFor="promo-status">
            <Select
              id="promo-status"
              value={form.status}
              onChange={(event) => update("status", event.target.value)}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Customer-facing headline" htmlFor="promo-headline">
            <Input
              id="promo-headline"
              value={form.headline}
              maxLength={160}
              onChange={(event) => update("headline", event.target.value)}
              placeholder="15% off your first order"
            />
          </Field>
          <Field label="Priority (higher wins when several qualify)" htmlFor="promo-priority">
            <Input
              id="promo-priority"
              type="number"
              min={0}
              value={form.priority}
              onChange={(event) => update("priority", event.target.value)}
            />
          </Field>
        </div>

        <Field label="Customer-facing description (optional)" htmlFor="promo-description">
          <Textarea
            id="promo-description"
            rows={2}
            value={form.description}
            maxLength={400}
            onChange={(event) => update("description", event.target.value)}
            placeholder="Shown on the homepage banner and at checkout."
          />
        </Field>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Starts (optional)" htmlFor="promo-starts">
            <Input
              id="promo-starts"
              type="date"
              value={form.startsAt}
              onChange={(event) => update("startsAt", event.target.value)}
            />
          </Field>
          <Field label="Ends (optional)" htmlFor="promo-ends">
            <Input
              id="promo-ends"
              type="date"
              value={form.endsAt}
              onChange={(event) => update("endsAt", event.target.value)}
            />
          </Field>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Total use limit (optional)" htmlFor="promo-limit-total">
            <Input
              id="promo-limit-total"
              type="number"
              min={1}
              value={form.usageLimitTotal}
              onChange={(event) => update("usageLimitTotal", event.target.value)}
            />
          </Field>
          <Field label="Per-customer limit (optional)" htmlFor="promo-limit-customer">
            <Input
              id="promo-limit-customer"
              type="number"
              min={1}
              value={form.usageLimitPerCustomer}
              onChange={(event) => update("usageLimitPerCustomer", event.target.value)}
            />
          </Field>
          <Field label="Minimum order, ₹ (optional)" htmlFor="promo-min-subtotal">
            <Input
              id="promo-min-subtotal"
              type="number"
              min={0}
              step="0.01"
              value={form.minSubtotal}
              onChange={(event) => update("minSubtotal", event.target.value)}
            />
          </Field>
        </div>

        <Field label="What the promotion does" htmlFor="promo-action-type">
          <Select
            id="promo-action-type"
            value={form.actionType}
            onChange={(event) => update("actionType", event.target.value)}
          >
            {Object.entries(ACTION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>

        {form.actionType === "percentage_discount" ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Percent off" htmlFor="promo-percent">
              <Input
                id="promo-percent"
                type="number"
                min={0}
                max={100}
                step="0.01"
                value={form.percentOff}
                onChange={(event) => update("percentOff", event.target.value)}
              />
            </Field>
            <Field label="Maximum discount, ₹ (optional)" htmlFor="promo-max-discount">
              <Input
                id="promo-max-discount"
                type="number"
                min={0}
                step="0.01"
                value={form.maximumDiscount}
                onChange={(event) => update("maximumDiscount", event.target.value)}
              />
            </Field>
          </div>
        ) : null}

        {form.actionType === "fixed_discount" ? (
          <Field label="Amount off, ₹" htmlFor="promo-amount-off">
            <Input
              id="promo-amount-off"
              type="number"
              min={0}
              step="0.01"
              value={form.amountOff}
              onChange={(event) => update("amountOff", event.target.value)}
            />
          </Field>
        ) : null}

        <div className="flex justify-end gap-2 border-t border-line pt-3">
          <Button type="button" variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            <T>Cancel</T>
          </Button>
          <Button type="submit" variant="primary" disabled={mutation.isPending}>
            {mutation.isPending ? <T>{"Creating..."}</T> : <T>{"Create promotion"}</T>}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function ManagePromotionModal({
  promotionId,
  onClose,
  onChanged,
}: {
  promotionId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [newCode, setNewCode] = useState("");
  const { data: promotion, isLoading } = useQuery({
    queryKey: ["admin-promotion", promotionId],
    queryFn: () => api.getPromotion(promotionId),
  });

  const addCoupon = useMutation({
    mutationFn: (code: string) => api.createCoupon(promotionId, code),
    onSuccess: async () => {
      setNewCode("");
      await queryClient.invalidateQueries({ queryKey: ["admin-promotion", promotionId] });
      onChanged();
      toast.success("Coupon code added.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not add the code."),
  });

  const deleteCoupon = useMutation({
    mutationFn: (couponId: string) => api.deleteCoupon(couponId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-promotion", promotionId] });
      onChanged();
      toast.success("Coupon updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update the code."),
  });

  const queryClient = useQueryClient();

  return (
    <Modal title="Manage promotion" onClose={onClose}>
      {isLoading || !promotion ? (
        <p className="text-sm text-ink-muted">
          <T>Loading...</T>
        </p>
      ) : (
        <div className="space-y-5">
          <div>
            <p className="font-display text-lg text-ink">{promotion.name}</p>
            {promotion.headline ? (
              <p className="text-sm text-ink-muted">{promotion.headline}</p>
            ) : null}
            <p className="mt-1 text-xs text-ink-muted">
              {promotion.action ? (
                ACTION_LABELS[promotion.action.actionType]
              ) : (
                <T>{"No action configured"}</T>
              )}
              {promotion.action?.actionType === "percentage_discount"
                ? ` — ${((promotion.action.valueBasisPoints ?? 0) / 100).toFixed(2)}%`
                : null}
              {promotion.action?.actionType === "fixed_discount" && promotion.action.amountMinor
                ? ` — ${formatMoney(promotion.action.amountMinor, "INR")}`
                : null}
            </p>
          </div>

          <div>
            <h3 className="text-sm font-medium text-ink">
              <T>Coupon codes</T>
            </h3>
            {promotion.coupons.length === 0 ? (
              <p className="mt-1 text-sm text-ink-muted">
                <T>No codes yet — this promotion applies automatically to every eligible cart.</T>
              </p>
            ) : (
              <ul className="mt-2 divide-y divide-line rounded-md border border-line">
                {promotion.coupons.map((coupon) => (
                  <li
                    key={coupon.id}
                    className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                  >
                    <div>
                      <span className="font-mono text-sm text-ink">{coupon.code}</span>
                      <span className="ml-2 text-xs text-ink-muted">
                        {coupon.redemptionCount} use{coupon.redemptionCount === 1 ? "" : "s"}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusPill status={coupon.active ? "published" : "draft"} />
                      <Button
                        type="button"
                        variant="tertiary"
                        className="min-h-8 px-2.5 text-xs"
                        disabled={deleteCoupon.isPending}
                        onClick={() => deleteCoupon.mutate(coupon.id)}
                      >
                        <T>Remove</T>
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <form
              className="mt-3 flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                if (!newCode.trim()) return;
                addCoupon.mutate(newCode.trim());
              }}
            >
              <Input
                value={newCode}
                maxLength={32}
                placeholder="NEWCODE"
                aria-label="New coupon code"
                onChange={(event) => setNewCode(event.target.value)}
                className="flex-1"
              />
              <Button type="submit" variant="secondary" disabled={addCoupon.isPending}>
                <T>Add code</T>
              </Button>
            </form>
          </div>

          <div className="flex justify-end border-t border-line pt-3">
            <Button type="button" variant="secondary" onClick={onClose}>
              <T>Close</T>
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

export function PromotionsListPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const canManage = permissions.has("promotions.manage");
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [managingId, setManagingId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; name: string } | null>(null);
  const limit = 25;
  const offset = (page - 1) * limit;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-promotions", statusFilter, searchQuery, page],
    queryFn: () =>
      api.promotions({
        status: statusFilter || undefined,
        search: searchQuery || undefined,
        limit,
        offset,
      }),
  });
  const promotions = data?.items ?? [];

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["admin-promotions"] });
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deletePromotion(id),
    onSuccess: async (result) => {
      await invalidate();
      setConfirmDelete(null);
      toast.success(
        result.deleted ? "Promotion deleted." : "Promotion archived (it has been used).",
      );
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not remove the promotion."),
  });

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">
            <T>Coupons & Promotions</T>
          </h1>
          <p className="max-w-2xl text-sm text-ink-muted">
            <T>
              A promotion with no coupon codes applies automatically to every eligible cart. Add one
              or more codes to make it code-gated instead. The sitewide on/off switch is on Site
              Settings, next to the other storefront switches.
            </T>
          </p>
        </div>
        {canManage ? (
          <Button variant="primary" onClick={() => setCreating(true)}>
            <T>New promotion</T>
          </Button>
        ) : null}
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <div className="max-w-sm flex-1">
          <SearchBox
            value={searchQuery}
            onSearch={(value) => {
              setSearchQuery(value);
              setPage(1);
            }}
            placeholder="Search by name..."
            aria-label="Search promotions"
          />
        </div>
        <Select
          value={statusFilter}
          onChange={(event) => {
            setStatusFilter(event.target.value);
            setPage(1);
          }}
          aria-label="Filter by status"
        >
          <option value="">
            <T>All statuses</T>
          </option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
      </div>

      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>
              <T>Promotion</T>
            </Th>
            <Th>
              <T>Status</T>
            </Th>
            <Th>
              <T>Codes</T>
            </Th>
            <Th>
              <T>Redemptions</T>
            </Th>
            <Th>
              <T>Priority</T>
            </Th>
            {canManage ? (
              <Th>
                <T>Actions</T>
              </Th>
            ) : null}
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={canManage ? 6 : 5} />
        ) : promotions.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={canManage ? 6 : 5} className="px-3 py-8">
                <EmptyState
                  title="No promotions yet"
                  hint="Create one to run a sitewide discount or issue coupon codes."
                />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {promotions.map((entry) => (
              <tr key={entry.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <p className="font-medium text-ink">{entry.name}</p>
                  {entry.headline ? (
                    <p className="text-xs text-ink-muted">{entry.headline}</p>
                  ) : null}
                </Td>
                <Td>
                  <StatusPill status={entry.status} />
                </Td>
                <Td>{entry.couponCount}</Td>
                <Td>{entry.redemptionCount}</Td>
                <Td>{entry.priority}</Td>
                {canManage ? (
                  <Td>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="secondary" onClick={() => setManagingId(entry.id)}>
                        <T>Manage</T>
                      </Button>
                      <Button
                        variant="destructive"
                        onClick={() => setConfirmDelete({ id: entry.id, name: entry.name })}
                      >
                        <T>Delete</T>
                      </Button>
                    </div>
                  </Td>
                ) : null}
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      <Pagination page={page} onPageChange={setPage} rowCount={promotions.length} limit={limit} />

      {creating ? (
        <CreatePromotionModal onClose={() => setCreating(false)} onCreated={invalidate} />
      ) : null}

      {managingId ? (
        <ManagePromotionModal
          promotionId={managingId}
          onClose={() => setManagingId(null)}
          onChanged={invalidate}
        />
      ) : null}

      {confirmDelete ? (
        <ConfirmDialog
          title={`Remove "${confirmDelete.name}"?`}
          description="If this promotion has never been redeemed it is deleted outright; otherwise it is archived so its history is kept."
          confirmLabel="Remove"
          pendingLabel="Removing..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => deleteMutation.mutate(confirmDelete.id)}
        />
      ) : null}
    </div>
  );
}
