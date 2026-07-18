/**
 * Top-level crash guard for the admin SPA.
 *
 * `main.tsx` previously rendered the router with no error boundary: an
 * uncaught render error on any single page white-screened the entire console
 * with no recovery short of a manual reload. This wraps the router content —
 * a crash in one page is caught here, reported to Sentry if configured
 * (`lib/sentry.ts`), and replaced with a fallback that gets the operator back
 * to a working screen instead of a blank one.
 *
 * Must be a class component: `componentDidCatch`/`getDerivedStateFromError`
 * have no function-component/hook equivalent in React.
 */

import { AlertTriangle } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { captureError } from "../lib/sentry";
import { Button } from "./ui";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    captureError(error, { componentStack: errorInfo.componentStack ?? undefined });
  }

  private handleGoToDashboard = (): void => {
    // A hard navigation, not react-router's `navigate`: the render tree that
    // crashed may include the very router this boundary sits inside, so the
    // safest way back to a working app is a fresh document load.
    window.location.assign("/");
  };

  private handleReload = (): void => {
    window.location.reload();
  };

  override render(): ReactNode {
    const { error } = this.state;
    if (error === null) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-4 py-10">
        <div className="w-full max-w-md rounded-md border border-line bg-surface p-8 text-center shadow-card">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-danger/10 text-danger">
            <AlertTriangle size={22} aria-hidden />
          </div>
          <h1 className="mt-4 font-display text-xl text-ink">Something went wrong</h1>
          <p className="mt-2 text-sm text-ink-muted">
            This page hit an unexpected error. Reloading usually fixes it — if it keeps
            happening, let us know what you were doing when it broke.
          </p>
          {import.meta.env.DEV && error.message ? (
            <p className="mt-3 overflow-x-auto rounded-sm bg-canvas px-3 py-2 text-left text-xs text-ink-muted">
              {error.message}
            </p>
          ) : null}
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <Button type="button" variant="secondary" onClick={this.handleGoToDashboard}>
              Back to dashboard
            </Button>
            <Button type="button" variant="primary" onClick={this.handleReload}>
              Reload
            </Button>
          </div>
        </div>
      </div>
    );
  }
}
