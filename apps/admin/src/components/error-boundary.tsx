/**
 * Last-resort guard against a blank page. React unmounts the whole tree on
 * any uncaught render error when nothing catches it, and nothing here did --
 * this was the one gap in the app that turned any such error into a fully
 * blank screen with no way back short of a manual reload.
 *
 * Keyed by the current route in `main.tsx`: navigating to a different page
 * remounts the boundary fresh, so a crash on one page does not require a
 * full reload to get back to a working one.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "./ui";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class AdminErrorBoundary extends Component<Props, State> {
  override state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Admin console crashed while rendering:", error, info.componentStack);
  }

  override render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <main className="flex min-h-screen items-center justify-center bg-canvas px-6 text-center">
        <div className="max-w-md">
          <p className="font-display text-lg text-ink">Something went wrong</p>
          <p className="mt-2 text-sm text-ink-muted">
            This page hit an unexpected error and could not finish rendering. Reloading usually
            fixes it. If it keeps happening, share what you were doing when it happened with the
            engineering team.
          </p>
          <p className="mt-3 overflow-x-auto rounded-sm border border-line bg-surface px-3 py-2 text-left text-xs break-words text-ink-muted">
            {error.message}
          </p>
          <Button
            type="button"
            variant="primary"
            className="mt-4"
            onClick={() => window.location.reload()}
          >
            Reload page
          </Button>
        </div>
      </main>
    );
  }
}
