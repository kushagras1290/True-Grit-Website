/** Admin shell: permission-aware sidebar navigation, top bar, demo-mode notice. */

import { cn } from "@truegrit/ui";
import {
  ClipboardList,
  FolderTree,
  Image,
  LayoutDashboard,
  Package,
  ScrollText,
  ShoppingCart,
  Users,
  Warehouse,
} from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router";

import { demoMode } from "../lib/api";
import { useMe, usePermissions } from "../lib/permissions";

interface NavEntry {
  to: string;
  label: string;
  icon: ReactNode;
  permission: string | null;
}

const NAV_GROUPS: Array<{ heading: string; entries: NavEntry[] }> = [
  {
    heading: "Overview",
    entries: [
      { to: "/", label: "Dashboard", icon: <LayoutDashboard size={16} />, permission: null },
    ],
  },
  {
    heading: "Commerce",
    entries: [
      {
        to: "/products",
        label: "Products",
        icon: <Package size={16} />,
        permission: "products.view",
      },
      {
        to: "/categories",
        label: "Categories",
        icon: <FolderTree size={16} />,
        permission: "categories.view",
      },
      {
        to: "/inventory",
        label: "Inventory",
        icon: <Warehouse size={16} />,
        permission: "inventory.view",
      },
      {
        to: "/orders",
        label: "Orders",
        icon: <ShoppingCart size={16} />,
        permission: "orders.view",
      },
    ],
  },
  {
    heading: "Content",
    entries: [
      { to: "/media", label: "Media Library", icon: <Image size={16} />, permission: "media.view" },
    ],
  },
  {
    heading: "Configuration",
    entries: [
      { to: "/users", label: "Users & Roles", icon: <Users size={16} />, permission: "users.view" },
      {
        to: "/audit",
        label: "Audit Log",
        icon: <ScrollText size={16} />,
        permission: "audit.view",
      },
    ],
  },
];

export function Shell() {
  const permissions = usePermissions();
  const { data: me } = useMe();

  return (
    <div className="flex min-h-screen">
      <a
        href="#admin-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <aside className="hidden w-60 shrink-0 border-r border-line bg-surface md:block">
        <div className="border-b border-line px-5 py-5">
          <p className="font-display text-lg tracking-tight text-brand">TRUE GRIT</p>
          <p className="text-xs text-ink-muted">Operations console</p>
        </div>
        <nav aria-label="Admin navigation" className="space-y-6 px-3 py-5">
          {NAV_GROUPS.map((group) => {
            const visible = group.entries.filter(
              (entry) => entry.permission === null || permissions.has(entry.permission),
            );
            if (visible.length === 0) return null;
            return (
              <div key={group.heading}>
                <p className="px-2 pb-1.5 text-[11px] font-semibold tracking-[0.14em] text-ink-muted uppercase">
                  {group.heading}
                </p>
                <ul className="space-y-0.5">
                  {visible.map((entry) => (
                    <li key={entry.to}>
                      <NavLink
                        to={entry.to}
                        end={entry.to === "/"}
                        className={({ isActive }) =>
                          cn(
                            "flex min-h-9 items-center gap-2.5 rounded-sm px-2 text-sm",
                            isActive
                              ? "bg-subtle font-medium text-brand"
                              : "text-ink hover:bg-canvas",
                          )
                        }
                      >
                        {entry.icon}
                        {entry.label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-line bg-surface px-6 py-3">
          <div className="flex items-center gap-2 text-sm text-ink-muted">
            <ClipboardList size={16} aria-hidden />
            {demoMode ? (
              <span>
                Demo data mode — set <code className="text-xs">VITE_API_URL</code> to connect the
                API
              </span>
            ) : (
              <span>Connected</span>
            )}
          </div>
          <div className="text-sm text-ink">
            {me ? (
              <span>
                {me.displayName} <span className="text-ink-muted">· {me.email}</span>
              </span>
            ) : (
              <span className="text-ink-muted">Signing in…</span>
            )}
          </div>
        </header>
        <main id="admin-content" className="flex-1 px-6 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
