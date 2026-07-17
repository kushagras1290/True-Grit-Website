import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArchiveRestore } from "lucide-react";
import { useMemo, useState } from "react";

import {
  Button,
  DataTableShell,
  EmptyState,
  LoadingRows,
  PageHeader,
  StatusPill,
  Td,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api, type ArchiveKind, type ArchiveRow } from "../lib/api";
import { formatDateTime } from "../lib/format";

const FILTERS: Array<{ id: "all" | ArchiveKind; label: string }> = [
  { id: "all", label: "All" },
  { id: "product", label: "Products" },
  { id: "category", label: "Categories" },
  { id: "farm", label: "Farms" },
  { id: "page", label: "CMS pages" },
];

const INVALIDATE_BY_KIND: Record<ArchiveKind, string[]> = {
  product: ["admin-products", "inventory"],
  category: ["admin-categories"],
  farm: ["farms"],
  page: ["cms-pages"],
};

function kindLabel(kind: ArchiveKind) {
  if (kind === "page") return "CMS page";
  return kind;
}

export function ArchivePage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<"all" | ArchiveKind>("all");
  const archive = useQuery({ queryKey: ["archive"], queryFn: api.archive });
  const restore = useMutation({
    mutationFn: (row: ArchiveRow) => api.restoreArchiveItem(row.kind, row.id),
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["archive"] }),
        ...INVALIDATE_BY_KIND[result.kind].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      ]);
      toast.success(`${kindLabel(result.kind)} restored as draft.`);
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : "Could not restore archived item.");
    },
  });

  const rows = useMemo(() => {
    const items = archive.data ?? [];
    return filter === "all" ? items : items.filter((item) => item.kind === filter);
  }, [archive.data, filter]);

  return (
    <section>
      <PageHeader
        title="Archive"
        description="Recover hidden products, categories, farms and CMS pages."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map((entry) => (
          <button
            type="button"
            key={entry.id}
            onClick={() => setFilter(entry.id)}
            className={
              "min-h-9 rounded-sm border px-3 text-sm font-medium " +
              (filter === entry.id
                ? "border-brand bg-subtle text-brand"
                : "border-line-strong bg-surface text-ink hover:bg-canvas")
            }
          >
            {entry.label}
          </button>
        ))}
      </div>

      {archive.isLoading ? (
        <DataTableShell>
          <thead>
            <tr>
              <Th>Item</Th>
              <Th>Type</Th>
              <Th>Status</Th>
              <Th>Archived</Th>
              <Th>Updated by</Th>
              <Th>Actions</Th>
            </tr>
          </thead>
          <LoadingRows columns={6} />
        </DataTableShell>
      ) : archive.isError ? (
        <EmptyState
          title="Archive unavailable"
          hint={
            archive.error instanceof ApiError
              ? archive.error.message
              : "Could not load archived records."
          }
        />
      ) : rows.length === 0 ? (
        <EmptyState title="No archived records" hint="Archived items will appear here." />
      ) : (
        <DataTableShell>
          <thead>
            <tr>
              <Th>Item</Th>
              <Th>Type</Th>
              <Th>Status</Th>
              <Th>Archived</Th>
              <Th>Updated by</Th>
              <Th>Actions</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.kind}:${row.id}`} className="border-t border-line">
                <Td>
                  <div className="font-medium text-ink">{row.name}</div>
                  <div className="text-xs text-ink-muted">
                    /{row.slug}
                    {row.detail ? ` - ${row.detail}` : ""}
                  </div>
                </Td>
                <Td className="capitalize">{kindLabel(row.kind)}</Td>
                <Td>
                  <StatusPill status={row.status} />
                </Td>
                <Td>{formatDateTime(row.archivedAt)}</Td>
                <Td>{row.updatedBy}</Td>
                <Td>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => restore.mutate(row)}
                    disabled={restore.isPending}
                  >
                    <ArchiveRestore size={15} aria-hidden />
                    Restore
                  </Button>
                </Td>
              </tr>
            ))}
          </tbody>
        </DataTableShell>
      )}
    </section>
  );
}
