/** Dashboard: only actionable numbers, each linking to its operational view. */

import { useQuery } from "@tanstack/react-query";
import { Activity, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { Button, EmptyState, PageHeader, SearchBox, StatusPill } from "../components/ui";
import { api, demoMode } from "../lib/api";
import { formatDateTime, formatMoney } from "../lib/format";

const SEARCH_MIN_QUERY_LENGTH = 2;

interface DashboardSearchResultItem {
  id: string;
  to: string;
  primary: string;
  secondary: string;
}

interface DashboardSearchResultGroup {
  key: string;
  label: string;
  items: DashboardSearchResultItem[];
}

function StatCard({
  label,
  value,
  to,
  tone,
}: {
  label: string;
  value: string;
  to: string;
  tone?: "warn";
}) {
  return (
    <Link
      to={to}
      className="block rounded-md border border-line bg-surface px-4 py-4 shadow-card transition-opacity hover:opacity-85"
    >
      <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">{label}</p>
      <p className={`mt-1.5 font-display text-2xl ${tone === "warn" ? "text-accent" : "text-ink"}`}>
        {value}
      </p>
    </Link>
  );
}

export function DashboardPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const trimmedSearchQuery = searchQuery.trim();
  const searchActive = trimmedSearchQuery.length >= SEARCH_MIN_QUERY_LENGTH;
  const search = useQuery({
    queryKey: ["admin-search", trimmedSearchQuery],
    queryFn: () => api.search(trimmedSearchQuery),
    enabled: searchActive,
  });
  const searchResultGroups: DashboardSearchResultGroup[] = search.data
    ? [
        {
          key: "products",
          label: "Products",
          items: search.data.products.map((product) => ({
            id: product.id,
            to: `/products/${product.id}`,
            primary: product.name,
            secondary: product.sku,
          })),
        },
        {
          key: "orders",
          label: "Orders",
          items: search.data.orders.map((order) => ({
            id: order.id,
            to: `/orders/${order.id}`,
            primary: order.publicReference,
            secondary: order.customerEmail ?? "No email on file",
          })),
        },
        {
          key: "users",
          label: "Users",
          items: search.data.users.map((user) => ({
            id: user.id,
            to: "/users",
            primary: user.displayName,
            secondary: user.email,
          })),
        },
        {
          key: "categories",
          label: "Categories",
          items: search.data.categories.map((category) => ({
            id: category.id,
            to: `/categories/${category.id}`,
            primary: category.name,
            secondary: category.slug,
          })),
        },
      ].filter((group) => group.items.length > 0)
    : [];

  const liveQueryOptions = { refetchInterval: 10_000, refetchIntervalInBackground: true };
  const orders = useQuery({
    queryKey: ["orders"],
    queryFn: () => api.orders(),
    ...liveQueryOptions,
  });
  const inventory = useQuery({
    queryKey: ["inventory"],
    queryFn: () => api.inventory(),
    ...liveQueryOptions,
  });
  const audit = useQuery({ queryKey: ["audit"], queryFn: () => api.audit(), ...liveQueryOptions });
  const products = useQuery({
    queryKey: ["admin-products"],
    queryFn: () => api.products({ limit: 100 }),
    ...liveQueryOptions,
  });
  const categories = useQuery({
    queryKey: ["admin-categories"],
    queryFn: () => api.categories({ limit: 100 }),
    ...liveQueryOptions,
  });
  const homeBlocks = useQuery({
    queryKey: ["home-blocks"],
    queryFn: api.homeBlocks,
    ...liveQueryOptions,
  });

  const paidOrders = (orders.data ?? []).filter((order) => order.paymentStatus === "paid");
  const revenueMinor = paidOrders.reduce((sum, order) => sum + order.totalMinor, 0);
  const pendingFulfilment = (orders.data ?? []).filter(
    (order) => order.orderStatus === "confirmed" || order.orderStatus === "processing",
  ).length;
  const lowStock = (inventory.data ?? []).filter(
    (row) => row.onHand - row.reserved <= row.reorderThreshold,
  );
  const publishedProducts = (products.data ?? []).filter(
    (product) => product.status === "published",
  );
  const publicCategories = (categories.data ?? []).filter(
    (category) => category.visibility === "public",
  );
  const activeHomeBlocks = (homeBlocks.data ?? []).filter((block) => block.enabled);
  const fetching =
    orders.isFetching ||
    inventory.isFetching ||
    audit.isFetching ||
    products.isFetching ||
    categories.isFetching ||
    homeBlocks.isFetching;
  const lastUpdatedAt = Math.max(
    orders.dataUpdatedAt,
    inventory.dataUpdatedAt,
    audit.dataUpdatedAt,
    products.dataUpdatedAt,
    categories.dataUpdatedAt,
    homeBlocks.dataUpdatedAt,
  );
  const lastUpdatedLabel =
    lastUpdatedAt > 0
      ? new Intl.DateTimeFormat("en-IN", { timeStyle: "medium" }).format(lastUpdatedAt)
      : "Pending";

  function refreshAll() {
    void orders.refetch();
    void inventory.refetch();
    void audit.refetch();
    void products.refetch();
    void categories.refetch();
    void homeBlocks.refetch();
  }

  return (
    <div>
      <PageHeader
        title="Realtime overview"
        description="Live marketplace state, fulfilment pressure and publishing activity."
        actions={
          <Button type="button" variant="secondary" onClick={refreshAll}>
            <RefreshCw size={15} className={fetching ? "animate-spin" : ""} />
            Refresh
          </Button>
        }
      />

      <section className="mb-6" aria-labelledby="global-search-heading">
        <h2 id="global-search-heading" className="sr-only">
          Search products, orders, users and categories
        </h2>
        <SearchBox
          value={searchQuery}
          onSearch={setSearchQuery}
          placeholder="Search products, orders, users, categories…"
          aria-label="Search products, orders, users and categories"
        />
        {trimmedSearchQuery.length > 0 && (
          <div className="mt-3 rounded-md border border-line bg-surface shadow-card">
            {!searchActive ? (
              <p className="px-4 py-3 text-sm text-ink-muted">Keep typing to search…</p>
            ) : search.isFetching ? (
              <p className="px-4 py-3 text-sm text-ink-muted">Searching…</p>
            ) : searchResultGroups.length === 0 ? (
              <EmptyState title="No matches" hint={`Nothing found for "${trimmedSearchQuery}".`} />
            ) : (
              <div className="divide-y divide-line">
                {searchResultGroups.map((group) => (
                  <div key={group.key} className="px-4 py-3">
                    <p className="mb-2 text-xs font-semibold tracking-wide text-ink-muted uppercase">
                      {group.label}
                    </p>
                    <ul className="space-y-1">
                      {group.items.map((item) => (
                        <li key={item.id}>
                          <Link
                            to={item.to}
                            className="flex items-center justify-between gap-3 rounded-sm px-2 py-1.5 hover:bg-canvas"
                          >
                            <span className="text-sm font-medium text-ink">{item.primary}</span>
                            <span className="text-xs text-ink-muted">{item.secondary}</span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="mb-6 grid gap-4 border-y border-line bg-surface px-4 py-4 shadow-card md:grid-cols-4">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-sm bg-subtle text-brand">
            <Activity size={17} />
          </span>
          <div>
            <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">API mode</p>
            <p className="text-sm font-medium text-ink">
              {demoMode ? "Demo data" : "Live connected"}
            </p>
          </div>
        </div>
        <div>
          <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">
            Published products
          </p>
          <p className="text-lg font-medium text-ink">
            {publishedProducts.length}/{products.data?.length ?? 0}
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">
            Public categories
          </p>
          <p className="text-lg font-medium text-ink">
            {publicCategories.length}/{categories.data?.length ?? 0}
          </p>
        </div>
        <div>
          <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">Last sync</p>
          <p className="text-lg font-medium text-ink">{lastUpdatedLabel}</p>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Revenue (paid)" value={formatMoney(revenueMinor)} to="/orders" />
        <StatCard label="Orders" value={String(orders.data?.length ?? "—")} to="/orders" />
        <StatCard
          label="Pending fulfilment"
          value={String(pendingFulfilment)}
          to="/orders"
          tone={pendingFulfilment > 0 ? "warn" : undefined}
        />
        <StatCard
          label="Low stock variants"
          value={String(lowStock.length)}
          to="/inventory"
          tone={lowStock.length > 0 ? "warn" : undefined}
        />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="website-heading">
          <h2 id="website-heading" className="mb-3 font-display text-lg text-ink">
            Website publishing surface
          </h2>
          <div className="rounded-md border border-line bg-surface shadow-card">
            <div className="grid divide-y divide-line md:grid-cols-3 md:divide-x md:divide-y-0">
              <Link to="/products" className="px-4 py-4 hover:bg-canvas">
                <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">
                  Catalogue
                </p>
                <p className="mt-1 text-2xl font-medium text-ink">{publishedProducts.length}</p>
                <p className="text-xs text-ink-muted">items visible on storefront</p>
              </Link>
              <Link to="/categories" className="px-4 py-4 hover:bg-canvas">
                <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">
                  Navigation
                </p>
                <p className="mt-1 text-2xl font-medium text-ink">{publicCategories.length}</p>
                <p className="text-xs text-ink-muted">public collections</p>
              </Link>
              <Link to="/categories" className="px-4 py-4 hover:bg-canvas">
                <p className="text-xs font-semibold tracking-wide text-ink-muted uppercase">
                  Homepage
                </p>
                <p className="mt-1 text-2xl font-medium text-ink">{activeHomeBlocks.length}</p>
                <p className="text-xs text-ink-muted">active CMS blocks</p>
              </Link>
            </div>
          </div>
        </section>

        <section aria-labelledby="attention-heading">
          <h2 id="attention-heading" className="mb-3 font-display text-lg text-ink">
            Needs attention
          </h2>
          {lowStock.length === 0 ? (
            <EmptyState title="Nothing urgent" hint="Low-stock and exception queues are clear." />
          ) : (
            <ul className="divide-y divide-line rounded-md border border-line bg-surface shadow-card">
              {lowStock.map((row) => (
                <li
                  key={row.variantId}
                  className="flex items-center justify-between gap-3 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-ink">{row.productName}</p>
                    <p className="text-xs text-ink-muted">
                      {row.variantName} · {row.sku}
                    </p>
                  </div>
                  <div className="text-right">
                    <StatusPill
                      status={row.onHand - row.reserved <= 0 ? "out_of_stock" : "low_stock"}
                    />
                    <p className="mt-1 text-xs text-ink-muted">
                      {row.onHand - row.reserved} available · reorder at {row.reorderThreshold}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="activity-heading">
          <h2 id="activity-heading" className="mb-3 font-display text-lg text-ink">
            Recent administrative activity
          </h2>
          <ul className="divide-y divide-line rounded-md border border-line bg-surface shadow-card">
            {(audit.data ?? []).slice(0, 6).map((entry) => (
              <li key={entry.id} className="px-4 py-3">
                <p className="text-sm text-ink">
                  <span className="font-medium">{entry.actorName}</span>{" "}
                  <span className="text-ink-muted">{entry.action.replaceAll(".", " · ")}</span>
                </p>
                <p className="text-xs text-ink-muted">{formatDateTime(entry.createdAt)}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
