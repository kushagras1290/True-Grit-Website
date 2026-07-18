import { Link, useSearchParams } from "react-router";

/** Real navigation (updates `?page=`), not client-only state, so listing
 * pages stay bookmarkable, shareable and back-button-friendly under SSR. */
export function PageLinkPagination({
  page,
  pageSize,
  total,
}: {
  page: number;
  pageSize: number;
  total: number;
}) {
  const [searchParams] = useSearchParams();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  function hrefFor(targetPage: number): string {
    const next = new URLSearchParams(searchParams);
    if (targetPage <= 1) next.delete("page");
    else next.set("page", String(targetPage));
    const query = next.toString();
    return query ? `?${query}` : "";
  }

  return (
    <nav
      aria-label="Pagination"
      className="mt-10 flex items-center justify-between border-t border-line pt-6"
    >
      {page > 1 ? (
        <Link
          to={hrefFor(page - 1)}
          className="rounded-full border border-line-strong px-4 py-2 text-sm font-medium text-ink hover:bg-canvas"
        >
          Previous
        </Link>
      ) : (
        <span className="rounded-full border border-line px-4 py-2 text-sm text-ink-muted opacity-50">
          Previous
        </span>
      )}
      <p className="text-sm text-ink-muted">
        Page {page} of {totalPages}
      </p>
      {page < totalPages ? (
        <Link
          to={hrefFor(page + 1)}
          className="rounded-full border border-line-strong px-4 py-2 text-sm font-medium text-ink hover:bg-canvas"
        >
          Next
        </Link>
      ) : (
        <span className="rounded-full border border-line px-4 py-2 text-sm text-ink-muted opacity-50">
          Next
        </span>
      )}
    </nav>
  );
}
