/** Product bundles (migration 0062): curated sets of specific variants sold
 * together at a flat price. The discount is enforced server-side at checkout
 * (`services.bundles.resolve_bundle_discount`), not just displayed here --
 * this page only manages the catalogue definition: which variants, what
 * price. */

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
import { formatMoney } from "../lib/format";
import { usePermissions } from "../lib/permissions";

const STATUS_OPTIONS = ["draft", "active", "ended", "archived"];

interface BundleFormState {
  name: string;
  slug: string;
  description: string;
  status: string;
  bundlePrice: string;
  imageUrl: string;
  imageAlt: string;
}

const EMPTY_FORM: BundleFormState = {
  name: "",
  slug: "",
  description: "",
  status: "draft",
  bundlePrice: "",
  imageUrl: "",
  imageAlt: "",
};

function toMinor(rupees: string): number {
  const parsed = Number(rupees.trim());
  return Number.isFinite(parsed) ? Math.round(parsed * 100) : 0;
}

function CreateBundleModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (bundleId: string) => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState<BundleFormState>(EMPTY_FORM);

  function update<K extends keyof BundleFormState>(key: K, value: BundleFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  const mutation = useMutation({
    mutationFn: () =>
      api.createBundle({
        name: form.name.trim(),
        slug: form.slug.trim() || undefined,
        description: form.description.trim() || null,
        status: form.status,
        bundlePriceMinor: toMinor(form.bundlePrice),
        imageUrl: form.imageUrl.trim() || null,
        imageAlt: form.imageAlt.trim() || null,
      }),
    onSuccess: (result) => {
      toast.success("Bundle created — now add its items.");
      onCreated(result.id);
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not create the bundle."),
  });

  return (
    <Modal title="New bundle" onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (!form.name.trim()) {
            toast.error("Give the bundle a name.");
            return;
          }
          if (!form.bundlePrice.trim() || toMinor(form.bundlePrice) < 0) {
            toast.error("Set a bundle price.");
            return;
          }
          mutation.mutate();
        }}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Name" htmlFor="bndl-name">
            <Input
              id="bndl-name"
              value={form.name}
              maxLength={140}
              onChange={(event) => update("name", event.target.value)}
              placeholder="Mango & Greens Combo"
            />
          </Field>
          <Field label="Slug (optional)" htmlFor="bndl-slug">
            <Input
              id="bndl-slug"
              value={form.slug}
              maxLength={140}
              onChange={(event) => update("slug", event.target.value)}
              placeholder="mango-greens-combo"
            />
          </Field>
        </div>

        <Field label="Description (optional)" htmlFor="bndl-description">
          <Textarea
            id="bndl-description"
            rows={2}
            value={form.description}
            maxLength={500}
            onChange={(event) => update("description", event.target.value)}
          />
        </Field>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Bundle price, ₹" htmlFor="bndl-price">
            <Input
              id="bndl-price"
              type="number"
              min={0}
              step="0.01"
              value={form.bundlePrice}
              onChange={(event) => update("bundlePrice", event.target.value)}
            />
          </Field>
          <Field label="Status" htmlFor="bndl-status">
            <Select
              id="bndl-status"
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
          <Field label="Image URL (optional)" htmlFor="bndl-image-url">
            <Input
              id="bndl-image-url"
              value={form.imageUrl}
              onChange={(event) => update("imageUrl", event.target.value)}
              placeholder="/homepage-hero.png"
            />
          </Field>
          <Field label="Image alt text (optional)" htmlFor="bndl-image-alt">
            <Input
              id="bndl-image-alt"
              value={form.imageAlt}
              onChange={(event) => update("imageAlt", event.target.value)}
            />
          </Field>
        </div>

        <p className="text-xs text-ink-muted">
          Add items (which variants, how many of each) after creating the bundle, from Manage.
        </p>

        <div className="flex justify-end gap-2 border-t border-line pt-3">
          <Button type="button" variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating..." : "Create bundle"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function ItemPicker({
  existingVariantIds,
  onPick,
}: {
  existingVariantIds: string[];
  onPick: (variant: { variantId: string; sku: string; name: string; productName: string }) => void;
}) {
  const [query, setQuery] = useState("");
  const [pickedProductId, setPickedProductId] = useState<string | null>(null);

  const productSearch = useQuery({
    queryKey: ["bundle-item-product-search", query],
    queryFn: () => api.products({ search: query, limit: 8 }),
    enabled: query.trim().length > 1,
  });

  const productDetail = useQuery({
    queryKey: ["bundle-item-product-detail", pickedProductId],
    queryFn: () => api.getProduct(pickedProductId!),
    enabled: pickedProductId !== null,
  });

  return (
    <div className="rounded-md border border-line bg-canvas p-3">
      <label className="text-xs font-medium text-ink-muted" htmlFor="bndl-item-search">
        Find a product to add
      </label>
      <Input
        id="bndl-item-search"
        className="mt-1"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setPickedProductId(null);
        }}
        placeholder="Search by product name..."
      />
      {query.trim().length > 1 && !pickedProductId ? (
        <ul className="mt-2 max-h-40 divide-y divide-line overflow-y-auto rounded-sm border border-line bg-surface">
          {productSearch.isLoading ? (
            <li className="px-3 py-2 text-sm text-ink-muted">Searching...</li>
          ) : (productSearch.data ?? []).length === 0 ? (
            <li className="px-3 py-2 text-sm text-ink-muted">No products match.</li>
          ) : (
            (productSearch.data ?? []).map((product) => (
              <li key={product.id}>
                <button
                  type="button"
                  className="block w-full px-3 py-2 text-left text-sm text-ink hover:bg-canvas"
                  onClick={() => setPickedProductId(product.id)}
                >
                  {product.name}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}

      {pickedProductId && productDetail.data ? (
        <div className="mt-3 space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-ink-muted">
              Variants of {productDetail.data.name}
            </p>
            <button
              type="button"
              className="text-xs text-brand hover:underline"
              onClick={() => {
                setPickedProductId(null);
                setQuery("");
              }}
            >
              Change product
            </button>
          </div>
          {productDetail.data.variants.map((variant) => {
            const alreadyAdded = existingVariantIds.includes(variant.id);
            return (
              <div
                key={variant.id}
                className="flex items-center justify-between gap-2 rounded-sm border border-line bg-surface px-2.5 py-1.5 text-sm"
              >
                <span className="min-w-0 truncate text-ink">
                  {variant.name} <span className="text-xs text-ink-muted">({variant.sku})</span>
                </span>
                <Button
                  type="button"
                  variant="secondary"
                  className="min-h-8 shrink-0 px-2.5 text-xs"
                  disabled={alreadyAdded}
                  onClick={() =>
                    onPick({
                      variantId: variant.id,
                      sku: variant.sku,
                      name: variant.name,
                      productName: productDetail.data!.name,
                    })
                  }
                >
                  {alreadyAdded ? "Added" : "Add"}
                </Button>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function ManageBundleModal({
  bundleId,
  onClose,
  onChanged,
}: {
  bundleId: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data: bundle, isLoading } = useQuery({
    queryKey: ["admin-bundle", bundleId],
    queryFn: () => api.getBundle(bundleId),
  });

  const itemsMutation = useMutation({
    mutationFn: (items: { variantId: string; quantity: number }[]) =>
      api.replaceBundleItems(bundleId, items),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-bundle", bundleId] });
      onChanged();
    },
    onError: (error) =>
      toast.error(
        error instanceof ApiError ? error.message : "Could not update the bundle's items.",
      ),
  });

  const componentSumMinor = (bundle?.items ?? []).reduce(
    (sum, item) => sum + item.lineTotalMinor,
    0,
  );
  const savingsMinor = bundle ? Math.max(componentSumMinor - bundle.bundlePriceMinor, 0) : 0;

  return (
    <Modal title="Manage bundle" onClose={onClose}>
      {isLoading || !bundle ? (
        <p className="text-sm text-ink-muted">Loading...</p>
      ) : (
        <div className="space-y-5">
          <div>
            <p className="font-display text-lg text-ink">{bundle.name}</p>
            <p className="text-xs text-ink-muted">
              {formatMoney(bundle.bundlePriceMinor, "INR")} bundle price · items priced at{" "}
              {formatMoney(componentSumMinor, "INR")} separately
              {savingsMinor > 0
                ? ` · saves ${formatMoney(savingsMinor, "INR")}`
                : " · no savings yet"}
            </p>
          </div>

          <div>
            <h3 className="text-sm font-medium text-ink">Items in this bundle</h3>
            {bundle.items.length === 0 ? (
              <p className="mt-1 text-sm text-ink-muted">
                No items yet — add at least one below. Checkout only applies this bundle's discount
                when the basket has every item here, in at least these quantities.
              </p>
            ) : (
              <ul className="mt-2 divide-y divide-line rounded-md border border-line">
                {bundle.items.map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm text-ink">
                        {item.quantity} × {item.productName} — {item.variantName}
                      </p>
                      <p className="text-xs text-ink-muted">
                        {item.sku} · {formatMoney(item.unitPriceMinor, "INR")} each
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="tertiary"
                      className="min-h-8 px-2.5 text-xs"
                      disabled={itemsMutation.isPending}
                      onClick={() =>
                        itemsMutation.mutate(
                          bundle.items
                            .filter((entry) => entry.id !== item.id)
                            .map((entry) => ({
                              variantId: entry.variantId,
                              quantity: entry.quantity,
                            })),
                        )
                      }
                    >
                      Remove
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {bundle.items.length < 12 ? (
            <ItemPicker
              existingVariantIds={bundle.items.map((item) => item.variantId)}
              onPick={(variant) =>
                itemsMutation.mutate([
                  ...bundle.items.map((entry) => ({
                    variantId: entry.variantId,
                    quantity: entry.quantity,
                  })),
                  { variantId: variant.variantId, quantity: 1 },
                ])
              }
            />
          ) : (
            <p className="text-xs text-ink-muted">A bundle can hold at most 12 items.</p>
          )}

          <div className="flex justify-end border-t border-line pt-3">
            <Button type="button" variant="secondary" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}

export function BundlesListPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const permissions = usePermissions();
  const canManage = permissions.has("bundles.manage");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [managingId, setManagingId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; name: string } | null>(null);
  const limit = 25;
  const offset = (page - 1) * limit;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-bundles", statusFilter, page],
    queryFn: () => api.bundles({ status: statusFilter || undefined, limit, offset }),
  });
  const bundles = data?.items ?? [];

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["admin-bundles"] });
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteBundle(id),
    onSuccess: async () => {
      await invalidate();
      setConfirmDelete(null);
      toast.success("Bundle deleted.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete the bundle."),
  });

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-ink">Bundles</h1>
          <p className="max-w-2xl text-sm text-ink-muted">
            Curated sets of specific variants sold together at a flat price. Checkout applies the
            saving automatically once a basket holds every item in a bundle.
          </p>
        </div>
        {canManage ? (
          <Button variant="primary" onClick={() => setCreating(true)}>
            New bundle
          </Button>
        ) : null}
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <Select
          value={statusFilter}
          onChange={(event) => {
            setStatusFilter(event.target.value);
            setPage(1);
          }}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
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
            <Th>Bundle</Th>
            <Th>Status</Th>
            <Th>Items</Th>
            <Th>Price</Th>
            {canManage ? <Th>Actions</Th> : null}
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={canManage ? 5 : 4} />
        ) : bundles.length === 0 ? (
          <tbody>
            <tr>
              <td colSpan={canManage ? 5 : 4} className="px-3 py-8">
                <EmptyState
                  title="No bundles yet"
                  hint="Create one to sell a curated set of products together at a set price."
                />
              </td>
            </tr>
          </tbody>
        ) : (
          <tbody>
            {bundles.map((entry) => (
              <tr key={entry.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <p className="font-medium text-ink">{entry.name}</p>
                  {entry.description ? (
                    <p className="text-xs text-ink-muted">{entry.description}</p>
                  ) : null}
                </Td>
                <Td>
                  <StatusPill status={entry.status} />
                </Td>
                <Td>{entry.itemCount}</Td>
                <Td>{formatMoney(entry.bundlePriceMinor, "INR")}</Td>
                {canManage ? (
                  <Td>
                    <div className="flex flex-wrap gap-2">
                      <Button variant="secondary" onClick={() => setManagingId(entry.id)}>
                        Manage
                      </Button>
                      <Button
                        variant="destructive"
                        onClick={() => setConfirmDelete({ id: entry.id, name: entry.name })}
                      >
                        Delete
                      </Button>
                    </div>
                  </Td>
                ) : null}
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      <Pagination page={page} onPageChange={setPage} rowCount={bundles.length} limit={limit} />

      {creating ? (
        <CreateBundleModal
          onClose={() => setCreating(false)}
          onCreated={(bundleId) => {
            void invalidate();
            setManagingId(bundleId);
          }}
        />
      ) : null}

      {managingId ? (
        <ManageBundleModal
          bundleId={managingId}
          onClose={() => setManagingId(null)}
          onChanged={invalidate}
        />
      ) : null}

      {confirmDelete ? (
        <ConfirmDialog
          title={`Delete "${confirmDelete.name}"?`}
          description="This removes the bundle and its item list. Orders that already used it keep their own record."
          confirmLabel="Delete"
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => deleteMutation.mutate(confirmDelete.id)}
        />
      ) : null}
    </div>
  );
}
