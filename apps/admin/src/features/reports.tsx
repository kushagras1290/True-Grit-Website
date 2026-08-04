/** Owner reports console: a curated library of named, parameterized,
 * read-only report queries — never a free-text SQL box. Every run is
 * audit-logged server-side. Gated on `reports.query`, granted only to
 * super_admin, so this route effectively only ever renders for the owner. */

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  Button,
  DataTableShell,
  EmptyState,
  Field,
  Input,
  PageHeader,
  Td,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api } from "../lib/api";
import { T } from "../lib/i18n";

export function ReportsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["admin-reports"], queryFn: api.reports });
  const [selectedId, setSelectedId] = useState("");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const toast = useToast();
  const reports = data ?? [];
  const selected = reports.find((report) => report.id === selectedId);

  const runMutation = useMutation({
    mutationFn: () => api.runReport(selectedId, filters),
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not run report."),
  });

  function selectReport(id: string) {
    setSelectedId(id);
    setFilters({});
    runMutation.reset();
  }

  return (
    <div>
      <PageHeader
        title="Owner Reports"
        description="Pick a report, set optional filters, and run it. No free-text SQL ever reaches the database."
      />
      {isLoading ? (
        <p className="text-sm text-ink-muted">
          <T>Loading report library…</T>
        </p>
      ) : reports.length === 0 ? (
        <EmptyState title="No reports available" hint="Requires the reports.query permission." />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[18rem_minmax(0,1fr)]">
          <div className="space-y-2">
            {reports.map((report) => (
              <button
                key={report.id}
                type="button"
                className={`block w-full rounded-md border px-3 py-3 text-left text-sm ${
                  selectedId === report.id
                    ? "border-brand bg-subtle/60"
                    : "border-line bg-surface hover:bg-subtle/40"
                }`}
                onClick={() => selectReport(report.id)}
              >
                <span className="block font-medium text-ink">{report.label}</span>
                <span className="mt-1 block text-xs text-ink-muted">{report.description}</span>
              </button>
            ))}
          </div>

          <div>
            {!selected ? (
              <EmptyState title="Pick a report" hint="Choose a report from the list to run it." />
            ) : (
              <div className="space-y-4">
                {selected.params.length > 0 ? (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {selected.params.map((param) => (
                      <Field
                        key={param.key}
                        label={param.label}
                        htmlFor={`report-param-${param.key}`}
                      >
                        <Input
                          id={`report-param-${param.key}`}
                          placeholder={param.kind === "date" ? "YYYY-MM-DD" : "IN"}
                          value={filters[param.key] ?? ""}
                          onChange={(event) =>
                            setFilters((current) => ({
                              ...current,
                              [param.key]: event.target.value,
                            }))
                          }
                        />
                      </Field>
                    ))}
                  </div>
                ) : null}
                <Button
                  variant="primary"
                  disabled={runMutation.isPending}
                  onClick={() => runMutation.mutate()}
                >
                  {runMutation.isPending ? <T>{"Running…"}</T> : <T>{"Run report"}</T>}
                </Button>

                {runMutation.data ? (
                  runMutation.data.rows.length === 0 ? (
                    <EmptyState title="No rows returned" />
                  ) : (
                    <DataTableShell>
                      <thead className="bg-canvas">
                        <tr>
                          {runMutation.data.columns.map((column) => (
                            <Th key={column}>{column}</Th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {runMutation.data.rows.map((row, rowIndex) => (
                          <tr key={rowIndex} className="border-t border-line">
                            {row.map((value, cellIndex) => (
                              <Td key={cellIndex}>{value ?? "—"}</Td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </DataTableShell>
                  )
                ) : null}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
