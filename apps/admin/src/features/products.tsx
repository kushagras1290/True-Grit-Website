/** Product list (TanStack Table: search, sort) and a tabbed product editor. */

import { useQuery } from "@tanstack/react-query";
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
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowUpDown } from "lucide-react";
import { useMemo, useState } from "react";
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
  PageHeader,
  StatusPill,
  Td,
  Th,
} from "../components/ui";
import { api } from "../lib/api";
import { formatDate, formatMoney } from "../lib/format";
import { PermissionGate } from "../lib/permissions";

const columnHelper = createColumnHelper<AdminProductRow>();

export function ProductListPage() {
  const { data, isLoading } = useQuery({ queryKey: ["admin-products"], queryFn: api.products });
  const [globalFilter, setGlobalFilter] = useState("");
  const [sorting, setSorting] = useState<SortingState>([]);

  const columns = useMemo(
    () => [
      columnHelper.accessor("name", {
        header: "Product",
        cell: (info) => (
          <Link to={`/products/${info.row.original.id}`} className="font-medium text-brand hover:underline">
            {info.getValue()}
          </Link>
        ),
      }),
      columnHelper.accessor("sku", { header: "SKU" }),
      columnHelper.accessor("status", {
        header: "Status",
        cell: (info) => <StatusPill status={info.getValue()} />,
      }),
      columnHelper.accessor((row) => row.categories.join(", "), { id: "categories", header: "Categories" }),
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
            <Button variant="primary">New product</Button>
          </PermissionGate>
        }
      />
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
          <EmptyState title="No products match" hint="Adjust the search or clear filters." />
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

const EDITOR_TABS = ["General", "Variants", "Pricing", "Trust", "SEO"] as const;

export function ProductEditorPage() {
  const { id = "" } = useParams();
  const { data: product, isLoading } = useQuery({
    queryKey: ["admin-product", id],
    queryFn: () => api.productDetail(id),
  });
  const [tab, setTab] = useState<(typeof EDITOR_TABS)[number]>("General");
  const [saved, setSaved] = useState(false);

  const form = useForm<GeneralForm>({
    resolver: zodResolver(generalSchema),
    values: product
      ? { name: product.name, slug: product.slug, shortDescription: product.shortDescription }
      : undefined,
  });

  if (isLoading) return <p className="text-sm text-ink-muted">Loading product…</p>;
  if (!product) return <EmptyState title="Product not found" hint="It may have been archived." />;

  return (
    <div>
      <PageHeader
        title={product.name}
        description={`${product.farmName} · ${product.region}`}
        actions={
          <PermissionGate permission="products.publish">
            <Button variant="primary">Publish</Button>
          </PermissionGate>
        }
      />

      <div role="tablist" aria-label="Product editor sections" className="mb-5 flex gap-1 border-b border-line">
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
        <form
          className="max-w-xl space-y-5"
          onSubmit={form.handleSubmit(() => {
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
          })}
        >
          <Field label="Public name" htmlFor="name" error={form.formState.errors.name?.message}>
            <Input
              id="name"
              aria-describedby={form.formState.errors.name ? "name-error" : undefined}
              {...form.register("name")}
            />
          </Field>
          <Field label="Slug" htmlFor="slug" error={form.formState.errors.slug?.message}>
            <Input
              id="slug"
              aria-describedby={form.formState.errors.slug ? "slug-error" : undefined}
              {...form.register("slug")}
            />
          </Field>
          <Field
            label="Short description"
            htmlFor="shortDescription"
            error={form.formState.errors.shortDescription?.message}
          >
            <Input
              id="shortDescription"
              aria-describedby={
                form.formState.errors.shortDescription ? "shortDescription-error" : undefined
              }
              {...form.register("shortDescription")}
            />
          </Field>
          <div className="flex items-center gap-3">
            <Button type="submit" variant="primary" disabled={form.formState.isSubmitting}>
              Save draft
            </Button>
            <span role="status" className="text-sm text-success">
              {saved ? "Saved" : ""}
            </span>
          </div>
        </form>
      ) : null}

      {tab === "Variants" ? (
        <DataTableShell>
          <thead className="bg-canvas">
            <tr>
              <Th>Variant</Th>
              <Th>SKU</Th>
              <Th>List price</Th>
              <Th>Sale price</Th>
              <Th>Availability</Th>
            </tr>
          </thead>
          <tbody>
            {product.variants.map((variant) => (
              <tr key={variant.id} className="border-t border-line">
                <Td className="font-medium">{variant.name}</Td>
                <Td>{variant.sku}</Td>
                <Td>{formatMoney(variant.listMinor)}</Td>
                <Td>{variant.saleMinor === null ? "—" : formatMoney(variant.saleMinor)}</Td>
                <Td>
                  <StatusPill status={variant.availability} />
                </Td>
              </tr>
            ))}
          </tbody>
        </DataTableShell>
      ) : null}

      {tab === "Pricing" ? (
        <p className="max-w-lg text-sm text-ink-muted">
          Prices are integer paise on active price rows per market (ADR-006). Historical orders
          snapshot their prices — changing a price here never rewrites an order.
        </p>
      ) : null}

      {tab === "Trust" ? (
        <div className="max-w-xl space-y-3">
          <p className="text-sm text-ink">
            <span className="font-medium">Certification:</span> {product.certification}
          </p>
          <ol className="space-y-2 border-l-2 border-subtle pl-4">
            {product.traceability.map((step) => (
              <li key={step.label}>
                <p className="text-sm font-medium text-ink">{step.label}</p>
                <p className="text-sm text-ink-muted">{step.detail}</p>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {tab === "SEO" ? (
        <dl className="max-w-xl space-y-3 text-sm">
          <div>
            <dt className="font-medium text-ink">Title</dt>
            <dd className="text-ink-muted">{product.seo.title}</dd>
          </div>
          <div>
            <dt className="font-medium text-ink">Description</dt>
            <dd className="text-ink-muted">{product.seo.description}</dd>
          </div>
          <div>
            <dt className="font-medium text-ink">Canonical</dt>
            <dd className="text-ink-muted">{product.seo.canonicalPath}</dd>
          </div>
        </dl>
      ) : null}
    </div>
  );
}
