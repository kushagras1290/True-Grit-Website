/**
 * Shop-page browse surfaces: the department rail, the sticky section bar and
 * the category index (sidebar on desktop, drawer on mobile).
 *
 * Each has one job, so the page never repeats itself:
 *
 *   - `DepartmentRail` is *discovery* — a single scrollable row of photographic
 *     department tiles, shown only while nothing is filtered.
 *   - `ShopSectionBar` is the *boundary* between browsing and buying, and the
 *     jump navigation between them.
 *   - `CategoryIndex` is *narrowing* — the full tree as text, driving the
 *     `?category=` filter.
 *
 * Filtering is real navigation (`?category=<slug>`), never client state, so a
 * filtered grid stays server-rendered, bookmarkable and back-button-friendly,
 * exactly like `PageLinkPagination`.
 */

import type { CategorySummary, CategoryTreeNode } from "@truegrit/contracts";
import { SlidersHorizontal, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { CategoryChip, CategoryTile } from "./catalogue";
import { Slider } from "./slider";

export const DEPARTMENTS_ANCHOR = "departments";
export const PRODUCTS_ANCHOR = "products";

/** Selecting a category resets pagination — page 4 of the old filter is
 * meaningless under the new one, and would usually land on an empty page. */
function filterHref(searchParams: URLSearchParams, slug: string | null): string {
  const next = new URLSearchParams(searchParams);
  next.delete("page");
  if (slug) next.set("category", slug);
  else next.delete("category");
  const query = next.toString();
  return query ? `?${query}` : "?";
}

/* ------------------------------------------------------------------------- */
/* Option A — the discovery rail                                              */
/* ------------------------------------------------------------------------- */

/**
 * Departments as one horizontal, scroll-snapping row of image tiles.
 *
 * A grid of every category is what made this page unusable: 134 portrait tiles
 * is roughly 34 rows before the first product. A rail is a fixed ~380px
 * regardless of how many departments exist, and it is the same component the
 * homepage already uses for curated collections, so the two pages match.
 */
export function DepartmentRail({ tree }: { tree: CategoryTreeNode[] }) {
  if (tree.length === 0) return null;
  return (
    <Slider ariaLabel="Shop by department">
      {tree.map((node) => (
        <div
          key={node.department.id}
          className="w-[calc(66%-0.5rem)] shrink-0 snap-start sm:w-[calc(40%-0.6rem)] lg:w-[calc(25%-0.75rem)]"
        >
          <CategoryTile
            category={node.department}
            variant="rail"
            productCount={node.totalProductCount}
          />
        </div>
      ))}
    </Slider>
  );
}

/* ------------------------------------------------------------------------- */
/* Option B — the sticky section bar                                          */
/* ------------------------------------------------------------------------- */

/**
 * The boundary marker between the browse band and the product canvas.
 *
 * Two stacked sections separated only by a background tint read as one endless
 * scroll. This bar makes the split explicit and skippable: plain in-page
 * anchors (so they work before hydration), the live result count, and the
 * mobile entry point to the category drawer.
 *
 * `activeAnchor` is observed rather than derived from the URL hash, so the
 * highlight follows the scroll position instead of only the last click.
 */
export function ShopSectionBar({
  productTotal,
  activeFilter,
  onOpenIndex,
  showDepartments,
}: {
  productTotal: number;
  activeFilter: CategorySummary | null;
  onOpenIndex: () => void;
  showDepartments: boolean;
}) {
  const [activeAnchor, setActiveAnchor] = useState<string>(
    showDepartments ? DEPARTMENTS_ANCHOR : PRODUCTS_ANCHOR,
  );

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return undefined;
    const sections = [DEPARTMENTS_ANCHOR, PRODUCTS_ANCHOR]
      .map((id) => document.getElementById(id))
      .filter((element): element is HTMLElement => element !== null);
    if (sections.length === 0) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        // The last section whose top edge has passed the bar wins, so the
        // highlight tracks reading position rather than intersection ratio.
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveAnchor(visible[0].target.id);
      },
      { rootMargin: "-30% 0px -60% 0px" },
    );
    for (const section of sections) observer.observe(section);
    return () => observer.disconnect();
  }, [showDepartments]);

  const segmentClass = (anchor: string) =>
    "rounded-full px-3 py-1.5 text-sm transition-colors " +
    (activeAnchor === anchor
      ? "bg-brand text-ink-inverse"
      : "text-ink-muted hover:text-ink hover:bg-canvas");

  return (
    <div className="sticky top-[var(--header-height)] z-30 border-y border-line bg-surface/95 backdrop-blur">
      <div className="mx-auto flex max-w-[80rem] items-center justify-between gap-3 px-4 py-2.5 sm:px-6">
        <nav aria-label="Shop sections" className="flex items-center gap-1">
          {showDepartments ? (
            <a href={`#${DEPARTMENTS_ANCHOR}`} className={segmentClass(DEPARTMENTS_ANCHOR)}>
              Departments
            </a>
          ) : null}
          <a href={`#${PRODUCTS_ANCHOR}`} className={segmentClass(PRODUCTS_ANCHOR)}>
            Products
          </a>
        </nav>

        <div className="flex items-center gap-3">
          <p className="hidden text-sm text-ink-muted sm:block" role="status">
            {activeFilter ? `${activeFilter.name} · ` : ""}
            {productTotal} product{productTotal === 1 ? "" : "s"}
          </p>
          <button
            type="button"
            onClick={onOpenIndex}
            className="flex min-h-11 items-center gap-1.5 rounded-full border border-line-strong px-3.5 text-sm font-medium text-ink hover:bg-canvas lg:hidden"
          >
            <SlidersHorizontal size={15} aria-hidden />
            {activeFilter ? activeFilter.name : "All categories"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------------- */
/* Option C — the category index                                              */
/* ------------------------------------------------------------------------- */

function IndexLink({
  label,
  count,
  href,
  active,
  onNavigate,
  indented = false,
}: {
  label: string;
  count: number;
  href: string;
  active: boolean;
  onNavigate?: () => void;
  indented?: boolean;
}) {
  return (
    <Link
      to={href}
      onClick={onNavigate}
      aria-current={active ? "true" : undefined}
      className={
        "flex items-baseline justify-between gap-2 rounded-sm py-1.5 pr-2 text-sm " +
        (indented ? "pl-3 " : "pl-2 ") +
        (active
          ? "bg-subtle/60 font-medium text-brand"
          : "text-ink hover:bg-canvas hover:text-brand")
      }
    >
      <span>{label}</span>
      <span className="shrink-0 text-xs text-ink-muted">{count}</span>
    </Link>
  );
}

/**
 * The whole catalogue tree as text: departments as `<details>` disclosures,
 * subcategories nested inside.
 *
 * Native `<details>` rather than JS state, so the tree is expandable before
 * hydration and keyboard-operable for free. The department containing the
 * active filter renders open.
 */
function CategoryIndexNav({
  tree,
  activeSlug,
  activeDepartmentId,
  onNavigate,
}: {
  tree: CategoryTreeNode[];
  activeSlug: string | null;
  activeDepartmentId: string | null;
  onNavigate?: () => void;
}) {
  const [searchParams] = useSearchParams();
  return (
    <nav aria-label="Categories">
      <IndexLink
        label="All products"
        count={tree.reduce((sum, node) => sum + node.totalProductCount, 0)}
        href={filterHref(searchParams, null)}
        active={activeSlug === null}
        onNavigate={onNavigate}
      />
      <ul className="mt-1 space-y-0.5">
        {tree.map((node) => {
          const departmentActive = node.department.slug === activeSlug;
          if (node.children.length === 0) {
            return (
              <li key={node.department.id}>
                <IndexLink
                  label={node.department.name}
                  count={node.totalProductCount}
                  href={filterHref(searchParams, node.department.slug)}
                  active={departmentActive}
                  onNavigate={onNavigate}
                />
              </li>
            );
          }
          return (
            <li key={node.department.id}>
              <details open={node.department.id === activeDepartmentId} className="group">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-2 rounded-sm py-1.5 pr-2 pl-2 text-sm text-ink hover:bg-canvas [&::-webkit-details-marker]:hidden">
                  <span className={departmentActive ? "font-medium text-brand" : undefined}>
                    {node.department.name}
                  </span>
                  <span
                    aria-hidden
                    className="shrink-0 text-xs text-ink-muted transition-transform group-open:rotate-90"
                  >
                    ›
                  </span>
                </summary>
                <ul className="mt-0.5 mb-1 ml-2 space-y-0.5 border-l border-line pl-1">
                  <li>
                    <IndexLink
                      label={`All ${node.department.name.toLowerCase()}`}
                      count={node.totalProductCount}
                      href={filterHref(searchParams, node.department.slug)}
                      active={departmentActive}
                      onNavigate={onNavigate}
                      indented
                    />
                  </li>
                  {node.children.map((child) => (
                    <li key={child.id}>
                      <IndexLink
                        label={child.name}
                        count={child.productCount}
                        href={filterHref(searchParams, child.slug)}
                        active={child.slug === activeSlug}
                        onNavigate={onNavigate}
                        indented
                      />
                    </li>
                  ))}
                </ul>
              </details>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Sticky desktop sidebar. Scrolls independently of the product canvas, so a
 * 134-entry tree never stretches the page. */
export function CategorySidebar({
  tree,
  activeSlug,
  activeDepartmentId,
}: {
  tree: CategoryTreeNode[];
  activeSlug: string | null;
  activeDepartmentId: string | null;
}) {
  return (
    <aside className="hidden lg:block">
      <div className="sticky top-[calc(var(--header-height)+4rem)] max-h-[calc(100vh-var(--header-height)-6rem)] overflow-y-auto pr-2">
        <p className="mb-2 px-2 text-xs font-semibold tracking-[0.14em] text-accent uppercase">
          Browse
        </p>
        <CategoryIndexNav
          tree={tree}
          activeSlug={activeSlug}
          activeDepartmentId={activeDepartmentId}
        />
      </div>
    </aside>
  );
}

/**
 * The same index as a mobile drawer. Dismisses on backdrop click, Escape and
 * navigation, and locks background scroll while open — matching the header's
 * existing overlay behaviour.
 */
export function CategoryDrawer({
  tree,
  activeSlug,
  activeDepartmentId,
  open,
  onClose,
}: {
  tree: CategoryTreeNode[];
  activeSlug: string | null;
  activeDepartmentId: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return undefined;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <button
        type="button"
        aria-label="Close categories"
        onClick={onClose}
        className="absolute inset-0 h-full w-full cursor-default bg-ink/40"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="absolute inset-y-0 left-0 flex w-[min(20rem,88vw)] flex-col bg-surface shadow-overlay outline-none"
      >
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <p id={titleId} className="font-display text-lg text-ink">
            Categories
          </p>
          <button
            type="button"
            onClick={onClose}
            className="flex min-h-11 min-w-11 items-center justify-center text-ink hover:text-brand"
            aria-label="Close categories"
          >
            <X size={19} aria-hidden />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 py-3">
          <CategoryIndexNav
            tree={tree}
            activeSlug={activeSlug}
            activeDepartmentId={activeDepartmentId}
            onNavigate={onClose}
          />
        </div>
      </div>
    </div>
  );
}

/**
 * Subcategory chips for the active department — the in-canvas drill-down that
 * takes over from the rail once a department is selected. Clicking the active
 * chip clears it, so the filter is reversible without hunting for a reset.
 */
export function SubcategoryChips({
  subcategories,
  activeSlug,
}: {
  subcategories: CategorySummary[];
  activeSlug: string | null;
}) {
  const [searchParams] = useSearchParams();
  if (subcategories.length === 0) return null;
  return (
    <ul className="mb-6 flex flex-wrap gap-2">
      {subcategories.map((subcategory) => {
        const active = subcategory.slug === activeSlug;
        return (
          <li key={subcategory.id}>
            <CategoryChip
              label={subcategory.name}
              count={subcategory.productCount}
              href={filterHref(searchParams, active ? null : subcategory.slug)}
              active={active}
            />
          </li>
        );
      })}
    </ul>
  );
}
