import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  DataTableShell,
  EmptyState,
  Field,
  LoadingRows,
  PageHeader,
  Pagination,
  Select,
  Td,
  Th,
} from "../components/ui";
import { api } from "../lib/api";

const LIMIT = 50;

function formatCell(value: string | number | null): string {
  if (value === null) return "NULL";
  return String(value);
}

export function DbBrowserPage() {
  const [selectedTable, setSelectedTable] = useState<string>("");
  const [page, setPage] = useState(1);
  const offset = (page - 1) * LIMIT;

  const { data: tables, isLoading: tablesLoading } = useQuery({
    queryKey: ["admin-db-browser-tables"],
    queryFn: () => api.dbBrowserTables(),
  });

  useEffect(() => {
    const firstTable = tables?.[0];
    if (!selectedTable && firstTable) {
      setSelectedTable(firstTable);
    }
  }, [tables, selectedTable]);

  const { data: table, isLoading: rowsLoading } = useQuery({
    queryKey: ["admin-db-browser-table", selectedTable, page],
    queryFn: () => api.dbBrowserTable(selectedTable, { limit: LIMIT, offset }),
    enabled: selectedTable.length > 0,
  });

  const columns = table?.columns ?? [];
  const rows = table?.rows ?? [];

  return (
    <div>
      <PageHeader
        title="SQL Tables"
        description="Owner-only. Read-only browser over every table — no arbitrary SQL is ever accepted from the client."
      />

      <div className="mb-6 max-w-xs">
        <Field label="Table" htmlFor="db-browser-table">
          <Select
            id="db-browser-table"
            value={selectedTable}
            disabled={tablesLoading || (tables ?? []).length === 0}
            onChange={(event) => {
              setSelectedTable(event.target.value);
              setPage(1);
            }}
          >
            {(tables ?? []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      {!selectedTable ? (
        <EmptyState title="No tables available" />
      ) : (
        <DataTableShell>
          <thead className="bg-canvas">
            <tr>
              {columns.map((column) => (
                <Th key={column}>{column}</Th>
              ))}
            </tr>
          </thead>
          {rowsLoading ? (
            <LoadingRows columns={Math.max(columns.length, 1)} />
          ) : (
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex} className="border-t border-line">
                  {row.map((cell, cellIndex) => (
                    <Td
                      key={cellIndex}
                      className={
                        cell === null ? "font-mono text-xs text-ink-muted" : "font-mono text-xs"
                      }
                    >
                      {formatCell(cell)}
                    </Td>
                  ))}
                </tr>
              ))}
            </tbody>
          )}
        </DataTableShell>
      )}
      {!rowsLoading && selectedTable && rows.length === 0 ? (
        <div className="mt-4">
          <EmptyState title="No rows in this table" />
        </div>
      ) : null}
      <Pagination page={page} onPageChange={setPage} rowCount={rows.length} limit={LIMIT} />
    </div>
  );
}
