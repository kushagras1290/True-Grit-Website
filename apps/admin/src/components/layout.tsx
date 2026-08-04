/** Admin shell: permission-aware sidebar navigation, top bar, demo-mode notice. */

import { cn } from "@truegrit/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArrowLeft,
  BarChart3,
  Bell,
  BookOpen,
  Boxes,
  ClipboardList,
  Database,
  FolderTree,
  HandHeart,
  Home,
  Image,
  Images,
  Inbox,
  KeyRound,
  LayoutDashboard,
  LineChart,
  LogOut,
  Mail,
  Menu,
  MessageCircle,
  MessageSquare,
  Package,
  Palette,
  PanelLeftClose,
  PanelLeftOpen,
  Percent,
  Receipt,
  Repeat,
  RotateCcw,
  ScrollText,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Sprout,
  Star,
  Terminal,
  Ticket,
  UtensilsCrossed,
  Users,
  Wallet,
  Warehouse,
  X,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";

import { Button } from "./ui";
import { api, demoMode, type AdminNotification } from "../lib/api";
import { useMe, usePermissions } from "../lib/permissions";
import { T } from "../lib/i18n";

const SIDEBAR_COLLAPSED_KEY = "truegrit.admin.sidebar-collapsed";

/** Nearest ancestor route for the back button: strips the last path segment
 * (`/products/prd_1` -> `/products`, `/products` -> `/`). Avoids relying on
 * browser history, which is unreliable after a direct link or refresh. */
function parentPath(pathname: string): string {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length <= 1) return "/";
  return `/${segments.slice(0, -1).join("/")}`;
}

interface NavEntry {
  to: string;
  label: string;
  icon: ReactNode;
  permission: string | string[] | null;
  /** Key into the `badges` map passed to SidebarNav — shows a small count
   * pill next to the label (e.g. pending submissions awaiting review). */
  badgeKey?: string;
  superAdminOnly?: boolean;
}

const NAV_GROUPS: Array<{ heading: string; entries: NavEntry[] }> = [
  {
    heading: "Overview",
    entries: [
      { to: "/", label: "Dashboard", icon: <LayoutDashboard size={16} />, permission: null },
      {
        to: "/analytics",
        label: "Analytics",
        icon: <LineChart size={16} />,
        permission: "analytics.view",
      },
      {
        to: "/messages",
        label: "Messages",
        icon: <MessageCircle size={16} />,
        permission: "messages.use",
        badgeKey: "messagesUnread",
      },
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
        to: "/price-adjustments",
        label: "Sale & Discounts",
        icon: <Percent size={16} />,
        permission: "settings.view",
      },
      {
        to: "/promotions",
        label: "Coupons & Promotions",
        icon: <Ticket size={16} />,
        permission: "promotions.view",
      },
      {
        to: "/bundles",
        label: "Bundles",
        icon: <Boxes size={16} />,
        permission: "bundles.view",
      },
      {
        to: "/subscriptions",
        label: "Subscriptions",
        icon: <Repeat size={16} />,
        permission: "subscriptions.view",
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
        to: "/farm-requests",
        label: "Farm Requests",
        icon: <HandHeart size={16} />,
        permission: "farm_requests.view",
        badgeKey: "farmRequestsOpen",
      },
      {
        to: "/orders",
        label: "Orders",
        icon: <ShoppingCart size={16} />,
        permission: "orders.view",
      },
      {
        to: "/returns",
        label: "Returns",
        icon: <RotateCcw size={16} />,
        permission: "returns.view",
      },
      {
        to: "/reviews",
        label: "Reviews",
        icon: <Star size={16} />,
        permission: "reviews.view",
        badgeKey: "reviewsPending",
      },
      {
        to: "/refunds",
        label: "Payments & Refunds",
        icon: <Receipt size={16} />,
        permission: "audit.view",
      },
      {
        to: "/revenue",
        label: "Revenue",
        icon: <Wallet size={16} />,
        permission: "revenue.view",
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
        to: "/homepage-settings",
        label: "Homepage Settings",
        icon: <Home size={16} />,
        permission: "settings.view",
      },
      {
        to: "/appearance",
        label: "Colours & Effects",
        icon: <Palette size={16} />,
        permission: "settings.view",
      },
      {
        to: "/site-control",
        label: "Site Settings",
        icon: <Settings size={16} />,
        permission: "settings.view",
      },
      { to: "/blog", label: "Blog", icon: <BookOpen size={16} />, permission: "articles.view" },
      {
        to: "/recipes",
        label: "Recipes",
        icon: <UtensilsCrossed size={16} />,
        permission: "recipes.view",
      },
      { to: "/media", label: "Media Library", icon: <Image size={16} />, permission: "media.view" },
      {
        to: "/image-guide",
        label: "Image Size Guide",
        icon: <Images size={16} />,
        permission: null,
      },
      {
        to: "/submissions",
        label: "Submissions",
        icon: <Inbox size={16} />,
        permission: "submissions.view",
        badgeKey: "submissionsPending",
      },
      {
        to: "/contact-attempts",
        label: "Contact Attempts",
        icon: <Mail size={16} />,
        permission: "users.view",
      },
    ],
  },
  {
    heading: "Community",
    entries: [
      {
        to: "/community",
        label: "Discussions",
        icon: <MessageSquare size={16} />,
        permission: "discussions.view",
      },
      {
        to: "/content-comments",
        label: "Post Comments",
        icon: <MessageSquare size={16} />,
        permission: "discussions.view",
      },
    ],
  },
  {
    heading: "Configuration",
    entries: [
      { to: "/users", label: "Users & Roles", icon: <Users size={16} />, permission: "users.view" },
      {
        to: "/scopes",
        label: "Scope Management",
        icon: <ShieldCheck size={16} />,
        permission: "users.manage_roles",
      },
      {
        to: "/audit",
        label: "Audit Log",
        icon: <ScrollText size={16} />,
        permission: "audit.view",
      },
      {
        to: "/reports",
        label: "Owner Reports",
        icon: <BarChart3 size={16} />,
        permission: "reports.query",
      },
      {
        to: "/admin-logs",
        label: "Admin Logs",
        icon: <Terminal size={16} />,
        permission: "audit.view",
        superAdminOnly: true,
      },
      {
        to: "/db-browser",
        label: "SQL Tables",
        icon: <Database size={16} />,
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
  isSuperAdmin,
  subtitle,
  onNavigate,
  collapsed = false,
  badges = {},
}: {
  permissions: ReadonlySet<string>;
  isSuperAdmin: boolean;
  subtitle: string;
  onNavigate?: () => void;
  collapsed?: boolean;
  badges?: Record<string, number>;
}) {
  return (
    <>
      {/* The storefront's mark, so the console reads as the same product rather
          than a separate tool. It stays visible when the sidebar collapses —
          that narrow rail is where the wordmark has to give way, not the logo. */}
      <div className={cn("border-b border-line py-5", collapsed ? "px-3" : "px-5")}>
        <div className={cn("flex items-center gap-2.5", collapsed && "justify-center")}>
          <img
            src="/brand/true-grit-mark.webp"
            alt=""
            width={32}
            height={32}
            className="h-8 w-8 shrink-0 rounded-full object-cover"
          />
          {collapsed ? null : (
            <p className="font-display text-lg tracking-tight text-brand">TRUE GRIT</p>
          )}
        </div>
        {collapsed ? null : <p className="mt-1.5 text-xs text-ink-muted">{subtitle}</p>}
      </div>
      <nav aria-label="Admin navigation" className="space-y-6 px-3 py-5">
        {NAV_GROUPS.map((group) => {
          const visible = group.entries.filter(
            (entry) =>
              (!entry.superAdminOnly || isSuperAdmin) &&
              (entry.permission === null ||
                (Array.isArray(entry.permission)
                  ? entry.permission.some((permission) => permissions.has(permission))
                  : permissions.has(entry.permission))),
          );
          if (visible.length === 0) return null;
          return (
            <div key={group.heading}>
              {collapsed ? null : (
                <p className="px-2 pb-1.5 text-[11px] font-semibold tracking-[0.14em] text-ink-muted uppercase">
                  {group.heading}
                </p>
              )}
              <ul className="space-y-0.5">
                {visible.map((entry) => (
                  <li key={entry.to}>
                    <NavLink
                      to={entry.to}
                      end={entry.to === "/"}
                      onClick={onNavigate}
                      title={collapsed ? entry.label : undefined}
                      aria-label={collapsed ? entry.label : undefined}
                      className={({ isActive }) =>
                        cn(
                          "flex min-h-9 items-center gap-2.5 rounded-sm px-2 text-sm",
                          collapsed && "justify-center px-0",
                          isActive
                            ? "bg-subtle font-medium text-brand"
                            : "text-ink hover:bg-canvas",
                        )
                      }
                    >
                      {entry.icon}
                      {collapsed ? null : (
                        <span className="flex flex-1 items-center justify-between gap-2">
                          {entry.label}
                          {entry.badgeKey && badges[entry.badgeKey] ? (
                            <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-brand px-1.5 py-0.5 text-[11px] font-semibold leading-none text-ink-inverse">
                              {badges[entry.badgeKey]}
                            </span>
                          ) : null}
                        </span>
                      )}
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

function NotificationPanel({
  items,
  total,
  onNavigate,
}: {
  items: AdminNotification[];
  total: number;
  onNavigate: (href: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        className="relative flex h-9 w-9 items-center justify-center rounded-sm text-ink hover:bg-canvas"
        aria-label={`Notifications${total ? `, ${total} pending` : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Bell size={17} />
        {total ? (
          <span className="absolute -top-1 -right-1 inline-flex min-w-5 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold leading-5 text-ink-inverse">
            {total > 99 ? "99+" : total}
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="absolute right-0 z-50 mt-2 w-[min(24rem,calc(100vw-2rem))] rounded-md border border-line bg-surface p-2 shadow-overlay">
          <div className="border-b border-line px-2 py-2">
            <p className="font-display text-base text-ink">
              <T>Notifications</T>
            </p>
            <p className="text-xs text-ink-muted">
              <T>Pending work for your role</T>
            </p>
          </div>
          <div className="max-h-96 overflow-y-auto py-1">
            {items.length ? (
              items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="flex w-full gap-3 rounded-sm px-2 py-3 text-left hover:bg-canvas"
                  onClick={() => {
                    setOpen(false);
                    onNavigate(item.href);
                  }}
                >
                  <span
                    className={cn(
                      "mt-0.5 inline-flex min-w-7 items-center justify-center rounded-full px-1.5 py-1 text-xs font-semibold",
                      item.severity === "danger"
                        ? "bg-danger/10 text-danger"
                        : item.severity === "info"
                          ? "bg-subtle text-brand"
                          : "bg-warning/10 text-warning",
                    )}
                  >
                    {item.count}
                  </span>
                  <span>
                    <span className="block text-sm font-medium text-ink">{item.title}</span>
                    <span className="mt-0.5 block text-xs leading-5 text-ink-muted">
                      {item.message}
                    </span>
                  </span>
                </button>
              ))
            ) : (
              <p className="px-2 py-6 text-center text-sm text-ink-muted">
                <T>Nothing pending.</T>
              </p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function Shell() {
  const permissions = usePermissions();
  const { data: me } = useMe();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(
    () => typeof window !== "undefined" && localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1",
  );
  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
  }, [collapsed]);
  const { data: pendingSubmissions } = useQuery({
    queryKey: ["submissions-pending-count"],
    queryFn: api.submissionsPendingCount,
    enabled: permissions.has("submissions.view"),
    refetchInterval: 60_000,
  });
  const { data: openFarmRequests } = useQuery({
    queryKey: ["farm-requests-open-count"],
    queryFn: api.farmRequestsOpenCount,
    enabled: permissions.has("farm_requests.view"),
    refetchInterval: 60_000,
  });
  const { data: pendingReviews } = useQuery({
    queryKey: ["reviews-pending-count"],
    queryFn: api.reviewsPendingCount,
    enabled: permissions.has("reviews.view"),
    refetchInterval: 60_000,
  });
  // No dedicated unread-count endpoint -- the conversation list already
  // carries each conversation's unreadCount, so the sidebar badge just sums
  // it client-side rather than adding a second endpoint for one number.
  // React Query dedupes this against the same ["conversations"] query
  // features/messages.tsx makes while the Messages page itself is open.
  const { data: conversations } = useQuery({
    queryKey: ["conversations"],
    queryFn: api.listConversations,
    enabled: permissions.has("messages.use"),
    refetchInterval: 60_000,
  });
  const badges = {
    submissionsPending: pendingSubmissions ?? 0,
    farmRequestsOpen: openFarmRequests ?? 0,
    reviewsPending: pendingReviews ?? 0,
    messagesUnread: (conversations ?? []).reduce((sum, c) => sum + c.unreadCount, 0),
  };
  const { data: notifications } = useQuery({
    queryKey: ["admin-notifications"],
    queryFn: api.notifications,
    refetchInterval: 60_000,
  });
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      queryClient.clear();
      navigate("/login", { replace: true });
    },
  });
  const subtitle = me?.farmName ? `Farm · ${me.farmName}` : "Operations console";
  const showBack = location.pathname !== "/";

  return (
    <div className="flex min-h-screen">
      <a
        href="#admin-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-surface focus:px-3 focus:py-2"
      >
        <T>Skip to content</T>
      </a>

      <aside
        className={cn(
          "hidden shrink-0 border-r border-line bg-surface transition-[width] duration-150 md:flex md:flex-col",
          collapsed ? "w-16" : "w-60",
        )}
      >
        <div className="flex-1 overflow-y-auto">
          <SidebarNav
            permissions={permissions}
            isSuperAdmin={me?.isSuperAdmin ?? false}
            subtitle={subtitle}
            collapsed={collapsed}
            badges={badges}
          />
        </div>
        <button
          type="button"
          className="flex min-h-10 items-center justify-center gap-2 border-t border-line text-xs text-ink-muted hover:bg-canvas hover:text-ink"
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          aria-pressed={collapsed}
          onClick={() => setCollapsed((value) => !value)}
        >
          {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          {collapsed ? null : <T>{"Collapse"}</T>}
        </button>
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
              isSuperAdmin={me?.isSuperAdmin ?? false}
              subtitle={subtitle}
              onNavigate={() => setMobileOpen(false)}
              badges={badges}
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
            {showBack ? (
              <button
                type="button"
                className="flex min-h-9 items-center gap-1.5 rounded-sm px-2 text-sm text-ink hover:bg-canvas"
                aria-label="Go back"
                onClick={() => navigate(parentPath(location.pathname))}
              >
                <ArrowLeft size={16} />
                <span className="hidden sm:inline">
                  <T>Back</T>
                </span>
              </button>
            ) : null}
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <ClipboardList size={16} aria-hidden className="hidden sm:block" />
              {demoMode ? (
                <span>
                  <T>Demo mode — set</T> <code className="text-xs">VITE_API_URL</code>{" "}
                  <T>to connect the API</T>
                </span>
              ) : (
                <span>
                  <T>Connected</T>
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm text-ink">
            <NotificationPanel
              items={notifications?.items ?? []}
              total={notifications?.total ?? 0}
              onNavigate={navigate}
            />
            {me ? (
              <span className="hidden sm:inline">
                {me.displayName} <span className="text-ink-muted">· {me.email}</span>
              </span>
            ) : (
              <span className="text-ink-muted">
                <T>Signing in…</T>
              </span>
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
