/** Admin shell: permission-aware sidebar navigation, top bar, demo-mode notice. */

import { cn } from "@truegrit/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ClipboardList,
  FolderTree,
  Image,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  ScrollText,
  Settings,
  ShoppingCart,
  Sprout,
  Users,
  Warehouse,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, Outlet, useNavigate } from "react-router";

import { Button } from "./ui";
import { api, demoMode } from "../lib/api";
import { useMe, usePermissions } from "../lib/permissions";

interface NavEntry {
  to: string;
  label: string;
  icon: ReactNode;
  permission: string | string[] | null;
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
        to: "/farms",
        label: "Farms",
        icon: <Sprout size={16} />,
        permission: "users.view",
      },
      {
        to: "/orders",
        label: "Orders",
        icon: <ShoppingCart size={16} />,
        permission: "orders.view",
      },
      {
        to: "/archive",
        label: "Archive",
        icon: <Archive size={16} />,
        permission: ["products.view", "categories.view", "users.view", "pages.view"],
      },
    ],
  },
  {
    heading: "Content",
    entries: [
      {
        to: "/site-control",
        label: "Site Control",
        icon: <Settings size={16} />,
        permission: "settings.view",
      },
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
      // No permission: everyone who can sign in owns their own password, farm
      // -scoped sub-admins included.
      { to: "/account", label: "Your Account", icon: <KeyRound size={16} />, permission: null },
    ],
  },
];

function SidebarNav({
  permissions,
  subtitle,
  onNavigate,
}: {
  permissions: ReadonlySet<string>;
  subtitle: string;
  onNavigate?: () => void;
}) {
  return (
    <>
      <div className="border-b border-line px-5 py-5">
        <p className="font-display text-lg tracking-tight text-brand">TRUE GRIT</p>
        <p className="text-xs text-ink-muted">{subtitle}</p>
      </div>
      <nav aria-label="Admin navigation" className="space-y-6 px-3 py-5">
        {NAV_GROUPS.map((group) => {
          const visible = group.entries.filter(
            (entry) =>
              entry.permission === null ||
              (Array.isArray(entry.permission)
                ? entry.permission.some((permission) => permissions.has(permission))
                : permissions.has(entry.permission)),
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
                      onClick={onNavigate}
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
    </>
  );
}

export function Shell() {
  const permissions = usePermissions();
  const { data: me } = useMe();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      queryClient.clear();
      navigate("/login", { replace: true });
    },
  });
  const subtitle = me?.farmName ? `Farm · ${me.farmName}` : "Operations console";

  return (
    <div className="flex min-h-screen">
      <a
        href="#admin-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      <aside className="hidden w-60 shrink-0 border-r border-line bg-surface md:block">
        <SidebarNav permissions={permissions} subtitle={subtitle} />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-label="Navigation">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-64 overflow-y-auto border-r border-line bg-surface">
            <div className="flex justify-end px-3 pt-3">
              <button
                type="button"
                aria-label="Close navigation"
                className="flex h-8 w-8 items-center justify-center text-ink-muted hover:text-ink"
                onClick={() => setMobileOpen(false)}
              >
                <X size={18} />
              </button>
            </div>
            <SidebarNav
              permissions={permissions}
              subtitle={subtitle}
              onNavigate={() => setMobileOpen(false)}
            />
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-line bg-surface px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="flex h-9 w-9 items-center justify-center rounded-sm text-ink hover:bg-canvas md:hidden"
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={18} />
            </button>
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <ClipboardList size={16} aria-hidden className="hidden sm:block" />
              {demoMode ? (
                <span>
                  Demo mode — set <code className="text-xs">VITE_API_URL</code> to connect the API
                </span>
              ) : (
                <span>Connected</span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm text-ink">
            {me ? (
              <span className="hidden sm:inline">
                {me.displayName} <span className="text-ink-muted">· {me.email}</span>
              </span>
            ) : (
              <span className="text-ink-muted">Signing in…</span>
            )}
            <Button
              type="button"
              variant="secondary"
              className="min-h-8 px-2.5"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              aria-label="Sign out"
            >
              <LogOut size={15} />
            </Button>
          </div>
        </header>
        <main id="admin-content" className="flex-1 px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
