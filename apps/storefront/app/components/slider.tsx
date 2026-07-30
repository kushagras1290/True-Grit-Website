/**
 * Horizontal slider for homepage collections.
 *
 * The track is a native scroll-snap flex row, so it works before hydration
 * and on touch devices; the arrow buttons are progressive enhancement that
 * appear only when content actually overflows the viewport. Item sizing is
 * the caller's job — wrap each child in `shrink-0 snap-start` with a width.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";

export function Slider({ ariaLabel, children }: { ariaLabel: string; children: ReactNode }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [canScrollBack, setCanScrollBack] = useState(false);
  const [canScrollForward, setCanScrollForward] = useState(false);

  function updateScrollState() {
    const track = trackRef.current;
    if (!track) return;
    setCanScrollBack(track.scrollLeft > 8);
    setCanScrollForward(track.scrollLeft + track.clientWidth < track.scrollWidth - 8);
  }

  useEffect(() => {
    updateScrollState();
    const track = trackRef.current;
    if (!track || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(updateScrollState);
    observer.observe(track);
    return () => observer.disconnect();
  }, []);

  function scrollByPage(direction: 1 | -1) {
    trackRef.current?.scrollBy({
      left: direction * trackRef.current.clientWidth * 0.9,
      behavior: "smooth",
    });
  }

  const arrowClass =
    "absolute top-1/2 z-10 flex h-10 w-10 -translate-y-1/2 items-center justify-center " +
    "rounded-full border border-line bg-surface/95 text-ink shadow-card transition-opacity " +
    "hover:bg-canvas";

  return (
    <div className="relative">
      <div
        ref={trackRef}
        role="region"
        aria-label={ariaLabel}
        onScroll={updateScrollState}
        className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {children}
      </div>
      {canScrollBack ? (
        <button
          type="button"
          aria-label="Scroll back"
          className={`${arrowClass} left-0 -translate-x-1/3`}
          onClick={() => scrollByPage(-1)}
        >
          <span aria-hidden>←</span>
        </button>
      ) : null}
      {canScrollForward ? (
        <button
          type="button"
          aria-label="Scroll forward"
          className={`${arrowClass} right-0 translate-x-1/3`}
          onClick={() => scrollByPage(1)}
        >
          <span aria-hidden>→</span>
        </button>
      ) : null}
    </div>
  );
}
