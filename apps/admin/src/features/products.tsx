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
  const { data, isLoading } = useQuery({ queryKey: ["admin-products"], queryFn: api.products });
  const [globalFilter, setGlobalFilter] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);
  const [creating, setCreating] = useState(false);

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

  return (
    <div>
      <PageHeader
        title="Products"
        description="Catalogue with live price and stock summaries."
        actions={
          <PermissionGate permission="products.create">
            <Button variant="primary" onClick={() => setCreating(true)}>
              New product
            </Button>
          </PermissionGate>
        }
      />
      {creating ? <CreateProductModal onClose={() => setCreating(false)} /> : null}

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
          <LoadingRows columns={8} />
        ) : (
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="border-t border-line hover:bg-canvas/60">
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
});

type GeneralForm = z.infer<typeof generalSchema>;

const seoSchema = z.object({
  seoTitle: z.string().max(160),
  seoDescription: z.string().max(320),
});

type SeoForm = z.infer<typeof seoSchema>;

const EDITOR_TABS = ["General", "Variants", "SEO"] as const;

export function ProductEditorPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<(typeof EDITOR_TABS)[number]>("General");

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

  const archiveMutation = useMutation({
    mutationFn: () => api.archiveProduct(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-products"] });
      toast.success("Product archived.");
      navigate("/products");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not archive."),
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
                onClick={() => {
                  if (
                    window.confirm("Archive this product? It will be hidden from the storefront.")
                  )
                    archiveMutation.mutate();
                }}
                disabled={archiveMutation.isPending}
              >
                Archive
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

function GeneralTab({
  product,
  onSave,
  saving,
}: {
  product: AdminProductDetail;
  onSave: (values: GeneralForm) => void;
  saving: boolean;
}) {
  const form = useForm<GeneralForm>({
    resolver: zodResolver(generalSchema),
    values: {
      name: product.name,
      slug: product.slug,
      shortDescription: product.shortDescription,
    },
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
