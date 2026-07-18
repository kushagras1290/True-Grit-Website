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
import { formatDateTime, formatMoney } from "../lib/format";

const LIMIT = 25;

export function RefundsOversightPage() {
  const [page, setPage] = useState(1);
  const offset = (page - 1) * LIMIT;
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin-refunds", page],
    queryFn: () => api.refunds({ limit: LIMIT, offset }),
  });
  const rows = data ?? [];

  return (
    <div>
      <PageHeader
        title="Payments & Refunds"
        description="Every refund issued across all orders, owner-only oversight of the Accounts role."
      />
      {isError ? (
        <EmptyState
          title="Refunds unavailable"
          hint="Only the owner can review payments and refunds."
        />
      ) : (
        <>
          <DataTableShell>
            <thead className="bg-canvas">
              <tr>
                <Th>Order</Th>
                <Th>Refunded by</Th>
                <Th>Amount</Th>
                <Th>Reason</Th>
                <Th>Provider ref</Th>
                <Th>When</Th>
              </tr>
            </thead>
            {isLoading ? (
              <LoadingRows columns={6} />
            ) : rows.length === 0 ? (
              <tbody>
                <tr>
                  <Td colSpan={6}>
                    <EmptyState title="No refunds issued yet" />
                  </Td>
                </tr>
              </tbody>
            ) : (
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t border-line">
                    <Td className="font-medium">{row.orderReference}</Td>
                    <Td>{row.actorName}</Td>
                    <Td>
                      {row.refundedMinor !== null
                        ? formatMoney(row.refundedMinor, row.currencyCode)
                        : "—"}
                    </Td>
                    <Td className="max-w-xs truncate" title={row.reason ?? ""}>
                      {row.reason || "—"}
                    </Td>
                    <Td className="font-mono text-xs">{row.providerRefundId || "—"}</Td>
                    <Td className="text-ink-muted">{formatDateTime(row.createdAt)}</Td>
                  </tr>
                ))}
              </tbody>
            )}
          </DataTableShell>
          <Pagination page={page} onPageChange={setPage} rowCount={rows.length} limit={LIMIT} />
        </>
      )}
    </div>
  );
}
