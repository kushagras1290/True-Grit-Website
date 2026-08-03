import { Link, useSearchParams } from "react-router";
import { LocalizedText, useLocalizeText } from "../lib/i18n/localized-text";

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
  const localize = useLocalizeText();
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
      aria-label={localize("Pagination")}
      className="mt-10 flex items-center justify-between border-t border-line pt-6"
    >
      {page > 1 ? (
        <Link
          to={hrefFor(page - 1)}
          className="rounded-full border border-line-strong px-4 py-2 text-sm font-medium text-ink hover:bg-canvas"
        >
          <LocalizedText>Previous</LocalizedText>
        </Link>
      ) : (
        <span className="rounded-full border border-line px-4 py-2 text-sm text-ink-muted opacity-50">
          <LocalizedText>Previous</LocalizedText>
        </span>
      )}
      <p className="text-sm text-ink-muted">
        <LocalizedText>Page</LocalizedText> {page} <LocalizedText>of</LocalizedText> {totalPages}
      </p>
      {page < totalPages ? (
        <Link
          to={hrefFor(page + 1)}
          className="rounded-full border border-line-strong px-4 py-2 text-sm font-medium text-ink hover:bg-canvas"
        >
          <LocalizedText>Next</LocalizedText>
        </Link>
      ) : (
        <span className="rounded-full border border-line px-4 py-2 text-sm text-ink-muted opacity-50">
          <LocalizedText>Next</LocalizedText>
        </span>
      )}
    </nav>
  );
}
