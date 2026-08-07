import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArchiveRestore } from "lucide-react";
import { useMemo, useState } from "react";

import {
  Button,
  ConfirmDialog,
  DataTableShell,
  EmptyState,
  LoadingRows,
  PageHeader,
  Pagination,
  SearchBox,
  StatusPill,
  Td,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api, type ArchiveKind, type ArchiveRow } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { T } from "../lib/i18n";

const FILTERS: Array<{ id: "all" | ArchiveKind; label: string }> = [
  { id: "all", label: "All" },
  { id: "product", label: "Products" },
  { id: "category", label: "Categories" },
  { id: "article", label: "Blog posts" },
  { id: "recipe", label: "Recipes" },
  { id: "farm", label: "Farms" },
  { id: "page", label: "CMS pages" },
];

const INVALIDATE_BY_KIND: Record<ArchiveKind, string[]> = {
  product: ["admin-products", "inventory"],
  category: ["admin-categories"],
  article: ["admin-articles"],
  recipe: ["admin-recipes"],
  farm: ["farms"],
  page: ["cms-pages"],
};

function kindLabel(kind: ArchiveKind) {
  if (kind === "page") return "CMS page";
  if (kind === "article") return "Blog post";
  return kind;
}

const ARCHIVE_PAGE_LIMIT = 25;

export function ArchivePage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<"all" | ArchiveKind>("all");
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const offset = (page - 1) * ARCHIVE_PAGE_LIMIT;
  const archive = useQuery({
    queryKey: ["archive", page, searchQuery],
    queryFn: () =>
      api.archive({ limit: ARCHIVE_PAGE_LIMIT, offset, search: searchQuery || undefined }),
  });
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

  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const allSelected =
    rows.length > 0 && rows.every((row) => selectedKeys.includes(`${row.kind}:${row.id}`));
  const selectedItems = rows.filter((row) => selectedKeys.includes(`${row.kind}:${row.id}`));

  const purgeMutation = useMutation({
    mutationFn: (items: Array<{ kind: ArchiveKind; id: string }>) => api.purgeArchiveItems(items),
    onSuccess: async (result) => {
      const kindsTouched = new Set(result.deleted.map((item) => item.kind));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["archive"] }),
        ...[...kindsTouched].flatMap((kind) =>
          INVALIDATE_BY_KIND[kind].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
        ),
      ]);
      setSelectedKeys([]);
      setConfirmingDelete(false);
      toast.success(`${result.count} item${result.count === 1 ? "" : "s"} permanently deleted.`);
    },
    onError: (error) => {
      toast.error(
        error instanceof ApiError
          ? error.message
          : "Could not permanently delete the selected items.",
      );
    },
  });

  function toggleRow(key: string) {
    setSelectedKeys((current) =>
      current.includes(key) ? current.filter((entry) => entry !== key) : [...current, key],
    );
  }

  function toggleAllRows() {
    setSelectedKeys(allSelected ? [] : rows.map((row) => `${row.kind}:${row.id}`));
  }

  return (
    <section>
      <PageHeader
        title="Archive"
        description="Recover hidden products, categories, farms and CMS pages."
        actions={
          selectedKeys.length > 0 ? (
            <Button
              variant="destructive"
              onClick={() => setConfirmingDelete(true)}
              disabled={purgeMutation.isPending}
            >
              <T>Delete selected (</T>
              {selectedKeys.length})
            </Button>
          ) : undefined
        }
      />
      {confirmingDelete ? (
        <ConfirmDialog
          title={
            selectedKeys.length === 1
              ? "Permanently delete item"
              : `Permanently delete ${selectedKeys.length} items`
          }
          description="This removes the selected items for good — they can no longer be restored. Items still referenced by orders or other records (for example a product with order history) will be skipped with an error."
          confirmLabel={selectedKeys.length === 1 ? "Delete forever" : "Delete forever"}
          pendingLabel="Deleting..."
          isPending={purgeMutation.isPending}
          onCancel={() => setConfirmingDelete(false)}
          onConfirm={() =>
            purgeMutation.mutate(selectedItems.map((row) => ({ kind: row.kind, id: row.id })))
          }
        />
      ) : null}

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

      <div className="mb-4 max-w-sm">
        <SearchBox
          value={searchQuery}
          onSearch={(value) => {
            setSearchQuery(value);
            setPage(1);
          }}
          placeholder="Search by name or slug…"
          aria-label="Search archive"
        />
      </div>

      {archive.isLoading ? (
        <DataTableShell>
          <thead>
            <tr>
              <Th>
                <T>Item</T>
              </Th>
              <Th>
                <T>Type</T>
              </Th>
              <Th>
                <T>Status</T>
              </Th>
              <Th>
                <T>Archived</T>
              </Th>
              <Th>
                <T>Updated by</T>
              </Th>
              <Th>
                <T>Actions</T>
              </Th>
            </tr>
          </thead>
          <LoadingRows columns={7} />
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
              <Th>
                <input
                  type="checkbox"
                  aria-label="Select all archived items"
                  checked={allSelected}
                  onChange={toggleAllRows}
                />
              </Th>
              <Th>
                <T>Item</T>
              </Th>
              <Th>
                <T>Type</T>
              </Th>
              <Th>
                <T>Status</T>
              </Th>
              <Th>
                <T>Archived</T>
              </Th>
              <Th>
                <T>Updated by</T>
              </Th>
              <Th>
                <T>Actions</T>
              </Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const key = `${row.kind}:${row.id}`;
              return (
                <tr key={key} className="border-t border-line">
                  <Td>
                    <input
                      type="checkbox"
                      aria-label={`Select ${row.name}`}
                      checked={selectedKeys.includes(key)}
                      onChange={() => toggleRow(key)}
                    />
                  </Td>
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
                      <T>Restore</T>
                    </Button>
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </DataTableShell>
      )}
      <Pagination
        page={page}
        onPageChange={setPage}
        rowCount={(archive.data ?? []).length}
        limit={ARCHIVE_PAGE_LIMIT}
      />
    </section>
  );
}
