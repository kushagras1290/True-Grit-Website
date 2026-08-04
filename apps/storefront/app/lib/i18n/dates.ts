/**
 * Locale-aware date formatting.
 *
 * `new Date(x).toLocaleDateString()` — with no locale argument — renders in
 * whatever locale the *runtime* defaults to. Server-side that is the Worker's
 * default (English); in the browser it is the operating system's. So a visitor
 * reading the site in Tamil saw English dates, and the server and client could
 * disagree about the same timestamp, which React reports as a hydration
 * mismatch. Passing the resolved locale explicitly fixes both at once.
 *
 * The timezone is pinned to UTC on purpose. Every timestamp the API returns is
 * UTC, and these are date-only displays (order placed, next delivery, comment
 * posted); formatting them in the viewer's zone would shift a late-evening
 * order to the previous day for some readers and not others, and would
 * reintroduce the server/client disagreement this module exists to remove.
 */

import { useCallback } from "react";

import { useLocaleContext } from "./context";

export type DateStyle = "short" | "medium" | "long";

/** Formats to a fixed, machine-readable shape when the value is unusable, so a
 *  malformed timestamp degrades to something diagnosable rather than the string
 *  "Invalid Date" in the middle of an order summary. */
const UNKNOWN_DATE = "—";

export function formatDate(
  locale: string,
  value: string | number | Date,
  style: DateStyle = "medium",
): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return UNKNOWN_DATE;
  try {
    return new Intl.DateTimeFormat(locale, { dateStyle: style, timeZone: "UTC" }).format(date);
  } catch {
    // An unsupported locale tag must not take a page down; ISO is readable in
    // every language and sorts correctly.
    return date.toISOString().slice(0, 10);
  }
}

/**
 * ```tsx
 * const formatDate = useDateFormatter();
 * <time dateTime={order.placedAt}>{formatDate(order.placedAt)}</time>
 * ```
 */
export function useDateFormatter(
  style: DateStyle = "medium",
): (value: string | number | Date) => string {
  const { locale } = useLocaleContext();
  return useCallback(
    (value: string | number | Date) => formatDate(locale, value, style),
    [locale, style],
  );
}
