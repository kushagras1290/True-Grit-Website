/** Product list (TanStack Table) + a real, wired product editor with a
 * create dialog, draft save, publish workflow and archive. */

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import type { AdminProductRow } from "@truegrit/contracts";
import { ArrowUpDown } from "lucide-react";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router";
import { z } from "zod";

import {
  Button,
  ConfirmDialog,
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
import { ApiError, api, type AdminProductDetail } from "../lib/api";
import { COUNTRIES } from "../lib/countries";
import { formatDate, formatMoney } from "../lib/format";
import { PermissionGate } from "../lib/permissions";

const columnHelper = createColumnHelper<AdminProductRow>();

const PRODUCT_TYPES = [
  "general",
  "fresh_fruit",
  "vegetable",
  "grain",
  "oil",
  "pantry",
  "dairy",
  "beverage",
];

const createSchema = z.object({
  name: z.string().min(3, "At least 3 characters").max(140),
  productType: z.string().min(1),
  slug: z
    .string()
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Lowercase letters, numbers and single hyphens")
    .optional()
    .or(z.literal("")),
});

type CreateForm = z.infer<typeof createSchema>;

function CreateProductModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: "", productType: "general", slug: "" },
  });

  const mutation = useMutation({
    mutationFn: (values: CreateForm) =>
      api.createProduct({
        name: values.name,
        productType: values.productType,
        slug: values.slug || undefined,
      }),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["admin-products"] });
      toast.success("Product created as a draft.");
      onClose();
      navigate(`/products/${result.id}`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not create the product."),
  });

  return (
    <Modal title="New product" onClose={onClose}>
      <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Public name" htmlFor="new-name" error={form.formState.errors.name?.message}>
          <Input id="new-name" placeholder="Organic Alphonso Mangoes" {...form.register("name")} />
        </Field>
        <Field label="Product type" htmlFor="new-type">
          <Select id="new-type" {...form.register("productType")}>
            {PRODUCT_TYPES.map((type) => (
              <option key={type} value={type}>
                {type.replaceAll("_", " ")}
              </option>
            ))}
          </Select>
        </Field>
        <Field
          label="Slug (optional — derived from the name if blank)"
          htmlFor="new-slug"
          error={form.formState.errors.slug?.message}
        >
          <Input id="new-slug" placeholder="organic-alphonso-mangoes" {...form.register("slug")} />
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating…" : "Create draft"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function ProductListPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["admin-products"], queryFn: api.products });
  const [globalFilter, setGlobalFilter] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);
  const [creating, setCreating] = useState(false);
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const deleteMutation = useMutation({
    mutationFn: (productIds: string[]) => api.deleteProducts(productIds),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["admin-products"] });
      setSelectedProductIds([]);
      setConfirmingDelete(false);
      toast.success(`${result.count} product${result.count === 1 ? "" : "s"} deleted.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete products."),
  });

  const columns = useMemo(
    () => [
      columnHelper.accessor("name", {
        header: "Product",
        cell: (info) => (
          <Link
            to={`/products/${info.row.original.id}`}
            className="font-medium text-brand hover:underline"
          >
            {info.getValue()}
          </Link>
        ),
      }),
      columnHelper.accessor("sku", { header: "SKU" }),
      columnHelper.accessor("status", {
        header: "Status",
        cell: (info) => <StatusPill status={info.getValue()} />,
      }),
      columnHelper.accessor((row) => row.categories.join(", "), {
        id: "categories",
        header: "Categories",
      }),
      columnHelper.accessor("farmName", { header: "Farm / brand" }),
      columnHelper.accessor("priceRange", { header: "Price (₹)" }),
      columnHelper.accessor("availableStock", { header: "Available" }),
      columnHelper.accessor("updatedAt", {
        header: "Updated",
        cell: (info) => formatDate(info.getValue()),
      }),
    ],
    [],
  );

  const table = useReactTable({
    data: data ?? [],
    columns,
    state: { globalFilter, sorting },
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  const visibleRows = table.getRowModel().rows;
  const allVisibleSelected =
    visibleRows.length > 0 &&
    visibleRows.every((row) => selectedProductIds.includes(row.original.id));

  function toggleProduct(productId: string) {
    setSelectedProductIds((current) =>
      current.includes(productId)
        ? current.filter((id) => id !== productId)
        : [...current, productId],
    );
  }

  function toggleVisibleProducts() {
    const visibleIds = visibleRows.map((row) => row.original.id);
    setSelectedProductIds((current) =>
      allVisibleSelected
        ? current.filter((id) => !visibleIds.includes(id))
        : Array.from(new Set([...current, ...visibleIds])),
    );
  }

  return (
    <div>
      <PageHeader
        title="Products"
        description="Catalogue with live price and stock summaries."
        actions={
          <div className="flex gap-2">
            <PermissionGate permission="products.edit">
              {selectedProductIds.length > 0 ? (
                <Button
                  variant="destructive"
                  onClick={() => setConfirmingDelete(true)}
                  disabled={deleteMutation.isPending}
                >
                  Delete selected ({selectedProductIds.length})
                </Button>
              ) : null}
            </PermissionGate>
            <PermissionGate permission="products.create">
              <Button variant="primary" onClick={() => setCreating(true)}>
                New product
              </Button>
            </PermissionGate>
          </div>
        }
      />
      {creating ? <CreateProductModal onClose={() => setCreating(false)} /> : null}
      {confirmingDelete ? (
        <ConfirmDialog
          title={
            selectedProductIds.length === 1
              ? "Delete product"
              : `Delete ${selectedProductIds.length} products`
          }
          description="Selected products will be hidden from the storefront and removed from the active catalogue."
          confirmLabel={selectedProductIds.length === 1 ? "Delete product" : "Delete products"}
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() => deleteMutation.mutate(selectedProductIds)}
        />
      ) : null}

      <div className="mb-4 max-w-sm">
        <label htmlFor="product-search" className="sr-only">
          Search products
        </label>
        <Input
          id="product-search"
          placeholder="Search by name, SKU, farm…"
          value={globalFilter}
          onChange={(event) => setGlobalFilter(event.target.value)}
        />
      </div>

      <DataTableShell>
        <thead className="bg-canvas">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              <Th>
                <input
                  type="checkbox"
                  aria-label="Select visible products"
                  checked={allVisibleSelected}
                  onChange={toggleVisibleProducts}
                />
              </Th>
              {headerGroup.headers.map((header) => (
                <Th key={header.id}>
                  {header.column.getCanSort() ? (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 uppercase"
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      <ArrowUpDown size={12} aria-hidden />
                    </button>
                  ) : (
                    flexRender(header.column.columnDef.header, header.getContext())
                  )}
                </Th>
              ))}
            </tr>
          ))}
        </thead>
        {isLoading ? (
          <LoadingRows columns={9} />
        ) : (
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="border-t border-line hover:bg-canvas/60">
                <Td>
                  <input
                    type="checkbox"
                    aria-label={`Select ${row.original.name}`}
                    checked={selectedProductIds.includes(row.original.id)}
                    onChange={() => toggleProduct(row.original.id)}
                  />
                </Td>
                {row.getVisibleCells().map((cell) => (
                  <Td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</Td>
                ))}
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      {!isLoading && table.getRowModel().rows.length === 0 ? (
        <div className="mt-4">
          <EmptyState title="No products match" hint="Adjust the search or create a product." />
        </div>
      ) : null}
    </div>
  );
}

const generalSchema = z.object({
  name: z.string().min(3, "Public name needs at least 3 characters").max(140),
  slug: z
    .string()
    .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/, "Lowercase letters, numbers and single hyphens only"),
  shortDescription: z.string().min(10, "Give customers at least one honest sentence").max(300),
  imageUrl: z.string().url("Enter a valid image URL").max(1000).or(z.literal("")),
  imageAlt: z.string().max(200),
});

type GeneralForm = z.infer<typeof generalSchema>;

const seoSchema = z.object({
  seoTitle: z.string().max(160),
  seoDescription: z.string().max(320),
});

type SeoForm = z.infer<typeof seoSchema>;

const EDITOR_TABS = ["General", "Variants", "Availability & Links", "SEO"] as const;

export function ProductEditorPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<(typeof EDITOR_TABS)[number]>("General");
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const {
    data: product,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["admin-product", id],
    queryFn: () => api.getProduct(id),
    retry: false,
  });

  const invalidate = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin-product", id] }),
      queryClient.invalidateQueries({ queryKey: ["admin-products"] }),
    ]);

  const saveMutation = useMutation({
    mutationFn: (input: Record<string, unknown>) => api.updateProduct(id, input),
    onSuccess: async () => {
      await invalidate();
      toast.success("Changes saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save changes."),
  });

  const publishMutation = useMutation({
    mutationFn: () => api.publishProduct(id),
    onSuccess: async (result) => {
      await invalidate();
      toast.success(`Published — version ${result.version} is now live.`);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not publish."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteProduct(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-products"] });
      toast.success("Product deleted from active catalogue.");
      navigate("/products");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not delete."),
  });

  if (isLoading) return <p className="text-sm text-ink-muted">Loading product…</p>;
  if (isError || !product)
    return <EmptyState title="Product not found" hint="It may have been archived." />;

  return (
    <div>
      <PageHeader
        title={product.name}
        description={`${product.farmName || "Unassigned"} · ${product.slug}`}
        actions={
          <div className="flex items-center gap-2">
            <StatusPill status={product.status} />
            <PermissionGate permission="products.edit">
              <Button
                variant="secondary"
                onClick={() => setConfirmingDelete(true)}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </Button>
            </PermissionGate>
            <PermissionGate
              permission="products.publish"
              fallback={
                <Button disabled title="Requires products.publish">
                  Publish
                </Button>
              }
            >
              <Button
                variant="primary"
                onClick={() => publishMutation.mutate()}
                disabled={publishMutation.isPending}
              >
                {publishMutation.isPending ? "Publishing…" : "Publish"}
              </Button>
            </PermissionGate>
          </div>
        }
      />
      {confirmingDelete ? (
        <ConfirmDialog
          title="Delete product"
          description={`${product.name} will be hidden from the storefront and removed from the active catalogue.`}
          confirmLabel="Delete product"
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() => deleteMutation.mutate()}
        />
      ) : null}

      <div
        role="tablist"
        aria-label="Product editor sections"
        className="mb-5 flex gap-1 border-b border-line"
      >
        {EDITOR_TABS.map((entry) => (
          <button
            key={entry}
            role="tab"
            aria-selected={tab === entry}
            onClick={() => setTab(entry)}
            className={`min-h-9 px-3 text-sm ${
              tab === entry
                ? "border-b-2 border-brand font-medium text-brand"
                : "text-ink-muted hover:text-ink"
            }`}
          >
            {entry}
          </button>
        ))}
      </div>

      {tab === "General" ? (
        <GeneralTab
          product={product}
          onSave={(values) => saveMutation.mutate(values)}
          saving={saveMutation.isPending}
        />
      ) : null}

      {tab === "Variants" ? (
        <DataTableShell>
          <thead className="bg-canvas">
            <tr>
              <Th>Variant</Th>
              <Th>SKU</Th>
              <Th>List price</Th>
              <Th>Sale price</Th>
              <Th>Available</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {product.variants.length === 0 ? (
              <tr className="border-t border-line">
                <Td className="text-ink-muted">No variants yet.</Td>
                <Td /> <Td /> <Td /> <Td /> <Td />
              </tr>
            ) : (
              product.variants.map((variant) => (
                <tr key={variant.id} className="border-t border-line">
                  <Td className="font-medium">{variant.name}</Td>
                  <Td>{variant.sku}</Td>
                  <Td>{variant.listMinor === null ? "—" : formatMoney(variant.listMinor)}</Td>
                  <Td>{variant.saleMinor === null ? "—" : formatMoney(variant.saleMinor)}</Td>
                  <Td>{variant.available}</Td>
                  <Td>
                    <StatusPill status={variant.status} />
                  </Td>
                </tr>
              ))
            )}
          </tbody>
        </DataTableShell>
      ) : null}

      {tab === "Availability & Links" ? (
        <AvailabilityTab
          product={product}
          onSave={(values) => saveMutation.mutate(values)}
          saving={saveMutation.isPending}
        />
      ) : null}

      {tab === "SEO" ? (
        <SeoTab
          product={product}
          onSave={(values) => saveMutation.mutate(values)}
          saving={saveMutation.isPending}
        />
      ) : null}
    </div>
  );
}

/** Geo release (global vs. selected countries) and the owner-curated
 * "linked products" slots shown on the product page — add, remove and reorder
 * to swap what customers see. */
function AvailabilityTab({
  product,
  onSave,
  saving,
}: {
  product: AdminProductDetail;
  onSave: (values: Record<string, unknown>) => void;
  saving: boolean;
}) {
  const [globalRelease, setGlobalRelease] = useState(product.releaseScope !== "selected");
  const [countries, setCountries] = useState<string[]>(product.releaseCountries);
  const [links, setLinks] = useState(product.linkedProducts);
  const [pendingLinkId, setPendingLinkId] = useState("");
  const { data: allProducts } = useQuery({ queryKey: ["admin-products"], queryFn: api.products });

  const dirty =
    globalRelease !== (product.releaseScope !== "selected") ||
    countries.join(",") !== product.releaseCountries.join(",") ||
    links.map((entry) => entry.id).join(",") !==
      product.linkedProducts.map((entry) => entry.id).join(",");

  const linkable = (allProducts ?? []).filter(
    (row) => row.id !== product.id && !links.some((entry) => entry.id === row.id),
  );

  function toggleCountry(code: string) {
    setCountries((current) =>
      current.includes(code) ? current.filter((entry) => entry !== code) : [...current, code],
    );
  }

  function moveLink(index: number, delta: number) {
    setLinks((current) => {
      const target = index + delta;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      const sourceItem = next[index];
      const targetItem = next[target];
      if (!sourceItem || !targetItem) return current;
      next[index] = targetItem;
      next[target] = sourceItem;
      return next;
    });
  }

  return (
    <div className="max-w-2xl space-y-8">
      <section className="space-y-3">
        <div>
          <h2 className="font-display text-lg text-ink">Where this product is released</h2>
          <p className="text-sm text-ink-muted">
            Visitors outside the released countries will not see this product anywhere on the
            storefront.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={globalRelease}
            onChange={(event) => setGlobalRelease(event.target.checked)}
          />
          Release globally (all countries)
        </label>
        {!globalRelease ? (
          <fieldset className="rounded-md border border-line p-4">
            <legend className="px-1 text-xs font-medium text-ink-muted">
              Release only in these countries
            </legend>
            <div className="grid max-h-64 grid-cols-2 gap-x-4 gap-y-1.5 overflow-y-auto sm:grid-cols-3">
              {COUNTRIES.map((country) => (
                <label key={country.code} className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={countries.includes(country.code)}
                    onChange={() => toggleCountry(country.code)}
                  />
                  {country.name}
                </label>
              ))}
            </div>
            {countries.length === 0 ? (
              <p className="mt-2 text-xs text-danger">
                Pick at least one country, or release globally.
              </p>
            ) : null}
          </fieldset>
        ) : null}
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="font-display text-lg text-ink">Linked products</h2>
          <p className="text-sm text-ink-muted">
            Shown in the “Goes well with” slots on this product’s page, in this order. Leave empty
            to let the storefront pick from the same category.
          </p>
        </div>
        {links.length === 0 ? (
          <p className="rounded-md border border-dashed border-line px-4 py-3 text-sm text-ink-muted">
            No products linked yet.
          </p>
        ) : (
          <ul className="divide-y divide-line rounded-md border border-line">
            {links.map((entry, index) => (
              <li key={entry.id} className="flex items-center gap-2 px-3 py-2 text-sm">
                <span className="w-5 text-xs text-ink-muted">{index + 1}.</span>
                <span className="flex-1 font-medium text-ink">{entry.name}</span>
                <StatusPill status={entry.status} />
                <button
                  type="button"
                  aria-label={`Move ${entry.name} up`}
                  className="min-h-8 min-w-8 rounded-sm border border-line text-xs disabled:opacity-40"
                  disabled={index === 0}
                  onClick={() => moveLink(index, -1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={`Move ${entry.name} down`}
                  className="min-h-8 min-w-8 rounded-sm border border-line text-xs disabled:opacity-40"
                  disabled={index === links.length - 1}
                  onClick={() => moveLink(index, 1)}
                >
                  ↓
                </button>
                <button
                  type="button"
                  aria-label={`Remove ${entry.name}`}
                  className="min-h-8 rounded-sm border border-line px-2 text-xs text-danger"
                  onClick={() =>
                    setLinks((current) => current.filter((link) => link.id !== entry.id))
                  }
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex gap-2">
          <Select
            aria-label="Product to link"
            value={pendingLinkId}
            onChange={(event) => setPendingLinkId(event.target.value)}
            className="flex-1"
          >
            <option value="">Add a product…</option>
            {linkable.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </Select>
          <Button
            type="button"
            variant="secondary"
            disabled={!pendingLinkId || links.length >= 12}
            onClick={() => {
              const row = linkable.find((entry) => entry.id === pendingLinkId);
              if (!row) return;
              setLinks((current) => [
                ...current,
                { id: row.id, name: row.name, slug: "", status: row.status },
              ]);
              setPendingLinkId("");
            }}
          >
            Link product
          </Button>
        </div>
      </section>

      <Button
        type="button"
        variant="primary"
        disabled={saving || !dirty || (!globalRelease && countries.length === 0)}
        onClick={() =>
          onSave({
            releaseScope: globalRelease ? "global" : "selected",
            releaseCountries: globalRelease ? [] : countries,
            linkedProductIds: links.map((entry) => entry.id),
          })
        }
      >
        {saving ? "Saving…" : "Save availability & links"}
      </Button>
    </div>
  );
}

function GeneralTab({
  product,
  onSave,
  saving,
}: {
  product: AdminProductDetail;
  onSave: (values: GeneralForm) => void;
  saving: boolean;
}) {
  const toast = useToast();
  const form = useForm<GeneralForm>({
    resolver: zodResolver(generalSchema),
    values: {
      name: product.name,
      slug: product.slug,
      shortDescription: product.shortDescription,
      imageUrl: product.imageUrl,
      imageAlt: product.imageAlt,
    },
  });
  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadImage(file),
    onSuccess: (result) => {
      form.setValue("imageUrl", result.url, { shouldDirty: true, shouldValidate: true });
      if (!form.getValues("imageAlt")) {
        form.setValue("imageAlt", product.name, { shouldDirty: true, shouldValidate: true });
      }
      toast.success("Image uploaded and URL updated.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not upload image."),
  });

  return (
    <form className="max-w-xl space-y-5" onSubmit={form.handleSubmit(onSave)}>
      <Field label="Public name" htmlFor="name" error={form.formState.errors.name?.message}>
        <Input id="name" {...form.register("name")} />
      </Field>
      <Field label="Slug" htmlFor="slug" error={form.formState.errors.slug?.message}>
        <Input id="slug" {...form.register("slug")} />
      </Field>
      <Field
        label="Short description"
        htmlFor="shortDescription"
        error={form.formState.errors.shortDescription?.message}
      >
        <Textarea id="shortDescription" {...form.register("shortDescription")} />
      </Field>
      <Field
        label="Customer image URL"
        htmlFor="imageUrl"
        error={form.formState.errors.imageUrl?.message}
      >
        <Input
          id="productImageUpload"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          className="mb-2"
          disabled={uploadMutation.isPending}
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            if (file) uploadMutation.mutate(file);
            event.currentTarget.value = "";
          }}
        />
        <Input
          id="imageUrl"
          type="url"
          placeholder={uploadMutation.isPending ? "Uploading image..." : "Image URL"}
          {...form.register("imageUrl")}
        />
      </Field>
      <Field
        label="Image alt text"
        htmlFor="imageAlt"
        error={form.formState.errors.imageAlt?.message}
      >
        <Input
          id="imageAlt"
          placeholder="A crate of ripe Alphonso mangoes"
          {...form.register("imageAlt")}
        />
      </Field>
      <Button type="submit" variant="primary" disabled={saving || !form.formState.isDirty}>
        {saving ? "Saving…" : "Save draft"}
      </Button>
    </form>
  );
}

function SeoTab({
  product,
  onSave,
  saving,
}: {
  product: AdminProductDetail;
  onSave: (values: SeoForm) => void;
  saving: boolean;
}) {
  const form = useForm<SeoForm>({
    resolver: zodResolver(seoSchema),
    values: { seoTitle: product.seoTitle, seoDescription: product.seoDescription },
  });

  return (
    <form className="max-w-xl space-y-5" onSubmit={form.handleSubmit(onSave)}>
      <Field label="SEO title" htmlFor="seoTitle" error={form.formState.errors.seoTitle?.message}>
        <Input id="seoTitle" {...form.register("seoTitle")} />
      </Field>
      <Field
        label="SEO description"
        htmlFor="seoDescription"
        error={form.formState.errors.seoDescription?.message}
      >
        <Textarea id="seoDescription" {...form.register("seoDescription")} />
      </Field>
      <Button type="submit" variant="primary" disabled={saving || !form.formState.isDirty}>
        {saving ? "Saving…" : "Save SEO"}
      </Button>
    </form>
  );
}
