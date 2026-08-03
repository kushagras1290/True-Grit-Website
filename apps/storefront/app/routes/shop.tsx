import { useState } from "react";
import { Link } from "react-router";

import type { Route } from "./+types/shop";
import { ProductGrid } from "../components/catalogue";
import { PageLinkPagination } from "../components/pagination";
import { RecommendedProducts } from "../components/recommendations";
import {
  CategoryDrawer,
  CategorySidebar,
  DEPARTMENTS_ANCHOR,
  DepartmentRail,
  PRODUCTS_ANCHOR,
  ShopSectionBar,
  SubcategoryChips,
} from "../components/shop-browse";
import {
  CATALOGUE_PAGE_SIZE,
  catalogueRuntime,
  loadBestsellers,
  loadCategories,
  loadProductPage,
} from "../lib/catalogue.server";
import { buildCategoryTree, findCategoryBranch } from "../lib/category-tree";
import { resolveCountry } from "../lib/geo.server";
import { resolveLocale } from "../lib/i18n/resolve.server";
import { seoMeta } from "../lib/seo";

export async function loader({ request, context }: Route.LoaderArgs) {
  const runtime = catalogueRuntime(context);
  const country = resolveCountry(request);
  const { locale } = resolveLocale(request);
  const url = new URL(request.url);

  const requestedPage = Number(url.searchParams.get("page") ?? "1");
  const pageNumber = Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const categorySlug = url.searchParams.get("category")?.trim() || null;

  const [categories, productPage, trending] = await Promise.all([
    loadCategories(country, runtime, locale.code),
    loadProductPage(pageNumber, country, runtime, categorySlug, locale.code),
    // Only worth showing on the unfiltered "All products" view -- a specific
    // department already has its own browsing grid, and a sitewide trending
    // row there would just compete with it.
    categorySlug
      ? Promise.resolve([])
      : loadBestsellers({ limit: 8 }, country, runtime, locale.code),
  ]);

  // Grouped server-side so the tree is serialized once rather than rebuilt by
  // the sidebar and the rail independently.
  const tree = buildCategoryTree(categories);
  const branch = findCategoryBranch(tree, categorySlug);

  return {
    tree,
    productPage,
    pageNumber,
    pageSize: CATALOGUE_PAGE_SIZE,
    // A slug that matches nothing published resolves to no branch; the grid is
    // empty too, so the page shows an explicit empty state instead of quietly
    // rendering the whole catalogue.
    activeSlug: branch.department || branch.subcategory ? categorySlug : null,
    activeDepartment: branch.department,
    activeSubcategory: branch.subcategory,
    unknownFilter: categorySlug !== null && !branch.department && !branch.subcategory,
    trending,
  };
}

export function meta(_args: Route.MetaArgs) {
  return seoMeta({
    title: "Shop the market",
    description:
      "Every product in the True Grit market — certified organic, traced to a verified farm.",
    canonicalPath: "/shop",
    indexing: "index",
  });
}

export default function Shop({ loaderData }: Route.ComponentProps) {
  const {
    tree,
    productPage,
    pageNumber,
    pageSize,
    activeSlug,
    activeDepartment,
    activeSubcategory,
    unknownFilter,
    trending,
  } = loaderData;
  const [drawerOpen, setDrawerOpen] = useState(false);

  const activeCategory = activeSubcategory ?? activeDepartment;
  // The rail is discovery, so it earns its space only when nothing is selected.
  // Once a department is active, its subcategory chips take over that role.
  const showRail = activeCategory === null;
  const departmentChildren =
    tree.find((node) => node.department.id === activeDepartment?.id)?.children ?? [];

  return (
    <>
      <header className="bg-canvas">
        <div className="mx-auto max-w-[80rem] px-4 pt-10 pb-8 sm:px-6 md:pt-14">
          <p className="text-xs font-semibold tracking-[0.14em] text-accent uppercase">
            The market
          </p>
          <div className="mt-2 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div className="max-w-3xl">
              <h1 className="font-display text-3xl leading-tight text-ink md:text-4xl">
                Shop the full organic catalogue
              </h1>
              <p className="mt-3 text-base text-ink-muted">
                Browse certified produce, pantry staples and seasonal harvests from verified farms.
              </p>
            </div>
            <p className="text-sm text-ink-muted">
              {tree.length} department{tree.length === 1 ? "" : "s"} · {productPage.total} product
              {productPage.total === 1 ? "" : "s"}
            </p>
          </div>
          <Link
            to="/bundles"
            className="mt-4 inline-flex min-h-9 items-center gap-1.5 rounded-full bg-subtle px-3.5 text-sm font-medium text-brand hover:opacity-90"
          >
            Buy in a set and save — see Bundles →
          </Link>
        </div>
      </header>

      {showRail ? (
        <section id={DEPARTMENTS_ANCHOR} className="bg-canvas scroll-mt-32">
          <div className="mx-auto max-w-[80rem] px-4 pb-10 sm:px-6">
            <h2 className="mb-4 font-display text-2xl leading-tight text-ink">
              Shop by department
            </h2>
            <DepartmentRail tree={tree} />
          </div>
        </section>
      ) : null}

      {showRail ? (
        <RecommendedProducts
          eyebrow="Right now"
          heading="Trending in the market"
          products={trending}
        />
      ) : null}

      <ShopSectionBar
        productTotal={productPage.total}
        activeFilter={activeCategory}
        onOpenIndex={() => setDrawerOpen(true)}
        showDepartments={showRail}
      />

      <section id={PRODUCTS_ANCHOR} className="scroll-mt-32 bg-surface">
        <div className="mx-auto grid max-w-[80rem] gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[16rem_minmax(0,1fr)] lg:py-14">
          <CategorySidebar
            tree={tree}
            activeSlug={activeSlug}
            activeDepartmentId={activeDepartment?.id ?? null}
          />

          <div>
            <div className="mb-6">
              <h2 className="font-display text-2xl leading-tight text-ink">
                {activeCategory ? activeCategory.name : "All products"}
              </h2>
              <p className="mt-1 text-sm text-ink-muted">
                {activeCategory?.shortDescription ??
                  "Every published product in the market, newest first."}
              </p>
            </div>

            <SubcategoryChips subcategories={departmentChildren} activeSlug={activeSlug} />

            {unknownFilter ? (
              <div className="rounded-md border border-dashed border-line-strong px-6 py-14 text-center">
                <p className="font-display text-lg text-ink">That category is not available</p>
                <p className="mt-1 text-sm text-ink-muted">
                  It may have been renamed, unpublished, or is not sold in your country.
                </p>
                <a
                  href="/shop"
                  className="mt-4 inline-block text-sm font-medium text-brand hover:underline"
                >
                  Browse the full market
                </a>
              </div>
            ) : (
              <>
                <ProductGrid products={productPage.items} />
                <PageLinkPagination
                  page={pageNumber}
                  pageSize={pageSize}
                  total={productPage.total}
                />
              </>
            )}
          </div>
        </div>
      </section>

      <CategoryDrawer
        tree={tree}
        activeSlug={activeSlug}
        activeDepartmentId={activeDepartment?.id ?? null}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </>
  );
}
