/**
 * A thin top-of-page progress bar during route transitions -- React Router's
 * own `useNavigation()` already tracks this (`state: "idle" | "loading" |
 * "submitting"`), so no extra data fetching or client state is needed here,
 * just a visual reflection of state the router already has.
 *
 * A brief transition can flash the bar for a single frame, which reads as a
 * glitch rather than feedback -- a short delay before showing it, and a
 * minimum-visible time once shown, keeps it from appearing for anything
 * fast enough that a customer would never consciously notice the wait.
 */

import { useEffect, useRef, useState } from "react";
import { useNavigation } from "react-router";

const SHOW_DELAY_MS = 150;
const MIN_VISIBLE_MS = 300;

export function NavigationProgress() {
  const navigation = useNavigation();
  const [visible, setVisible] = useState(false);
  const shownAtRef = useRef<number | null>(null);

  useEffect(() => {
    const isNavigating = navigation.state !== "idle";

    if (isNavigating) {
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
  }, [navigation.state]);

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-label="Loading"
      className="fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden bg-transparent print:hidden motion-reduce:hidden"
    >
      <div className="h-full w-full origin-left animate-[navigation-progress_1.1s_ease-in-out_infinite] bg-brand" />
    </div>
  );
}
