/**
 * A thin top-of-page progress bar while any TanStack Query fetch or mutation
 * is in flight -- route changes and save/publish actions both go through
 * TanStack Query here, so its global counters are a reliable "the app is
 * doing something" signal without wiring a loading flag through every page.
 *
 * Mirrors the storefront's `NavigationProgress` (same show-delay and
 * minimum-visible-time reasoning: a brief fetch flashing the bar for one
 * frame reads as a glitch, not feedback).
 */

import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

const SHOW_DELAY_MS = 150;
const MIN_VISIBLE_MS = 300;

export function TopProgressBar() {
  const isFetching = useIsFetching();
  const isMutating = useIsMutating();
  const active = isFetching > 0 || isMutating > 0;
  const [visible, setVisible] = useState(false);
  const shownAtRef = useRef<number | null>(null);

  useEffect(() => {
    if (active) {
      const showTimer = window.setTimeout(() => {
        shownAtRef.current = Date.now();
        setVisible(true);
      }, SHOW_DELAY_MS);
      return () => window.clearTimeout(showTimer);
    }

    if (shownAtRef.current === null) {
      setVisible(false);
      return;
    }
    const elapsed = Date.now() - shownAtRef.current;
    const remaining = Math.max(MIN_VISIBLE_MS - elapsed, 0);
    const hideTimer = window.setTimeout(() => {
      shownAtRef.current = null;
      setVisible(false);
    }, remaining);
    return () => window.clearTimeout(hideTimer);
  }, [active]);

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-label="Loading"
      className="fixed inset-x-0 top-0 z-[60] h-0.5 overflow-hidden bg-transparent motion-reduce:hidden"
    >
      <div className="h-full w-full origin-left animate-[admin-progress_1.1s_ease-in-out_infinite] bg-brand" />
    </div>
  );
}
