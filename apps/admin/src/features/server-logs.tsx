import { cn } from "@truegrit/ui";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  DataTableShell,
  EmptyState,
  LoadingRows,
  PageHeader,
  Pagination,
  Td,
  Th,
} from "../components/ui";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/format";

const LEVEL_STYLES: Record<string, string> = {
  error: "bg-danger/10 text-danger",
  warn: "bg-warning/10 text-warning",
  info: "bg-subtle text-brand",
};

function LevelPill({ level }: { level: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        LEVEL_STYLES[level] ?? "bg-canvas text-ink-muted border border-line",
      )}
    >
      {level}
    </span>
  );
}

const LIMIT = 50;

export function AdminLogsPage() {
  const [page, setPage] = useState(1);
  const offset = (page - 1) * LIMIT;

  const { data, isLoading } = useQuery({
    queryKey: ["admin-logs", page],
    queryFn: () => api.serverLogs({ limit: LIMIT, offset }),
  });

  const rows = data ?? [];

  return (
    <div>
      <PageHeader
        title="Admin Logs"
        description="Super-admin only. Application errors and unhandled exceptions, newest first."
      />
      <DataTableShell>
        <thead className="bg-canvas">
          <tr>
            <Th>Time</Th>
            <Th>Level</Th>
            <Th>Event</Th>
            <Th>Fields</Th>
          </tr>
        </thead>
        {isLoading ? (
          <LoadingRows columns={4} />
        ) : (
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-line align-top">
                <Td className="whitespace-nowrap font-mono text-xs text-ink-muted">
                  {formatDateTime(row.createdAt)}
                </Td>
                <Td>
                  <LevelPill level={row.level} />
                </Td>
                <Td className="font-medium">{row.event}</Td>
                <Td>
                  {Object.keys(row.fields).length === 0 ? (
                    <span className="text-ink-muted">—</span>
                  ) : (
                    <details>
                      <summary className="cursor-pointer text-sm text-brand">
                        {Object.keys(row.fields).length} field
                        {Object.keys(row.fields).length === 1 ? "" : "s"}
                      </summary>
                      <pre className="mt-2 max-w-xl overflow-x-auto rounded-sm border border-line bg-canvas p-2 text-xs text-ink">
                        {JSON.stringify(row.fields, null, 2)}
                      </pre>
                    </details>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        )}
      </DataTableShell>
      {!isLoading && rows.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title="No server errors logged"
            hint="5xx AppErrors and unhandled exceptions will show up here as they happen."
          />
        </div>
      ) : null}
      <Pagination page={page} onPageChange={setPage} rowCount={rows.length} limit={LIMIT} />
    </div>
  );
}
