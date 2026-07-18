import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { captureErrorMock } = vi.hoisted(() => ({ captureErrorMock: vi.fn() }));

vi.mock("../lib/sentry", () => ({
  captureError: captureErrorMock,
}));

import { ErrorBoundary } from "./error-boundary";

function Bomb(): never {
  throw new Error("kaboom");
}

afterEach(() => {
  captureErrorMock.mockClear();
  vi.restoreAllMocks();
});

describe("ErrorBoundary", () => {
  it("renders children when nothing has thrown", () => {
    render(
      <ErrorBoundary>
        <p>All good</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("All good")).toBeInTheDocument();
  });

  it("renders a fallback instead of crashing when a child throws during render", () => {
    // React logs the caught error to the console as part of its own
    // dev-mode reporting; silence it so the expected-error path doesn't spam
    // the test output.
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reload/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back to dashboard/i })).toBeInTheDocument();
  });

  it("reports the caught error to Sentry via lib/sentry's captureError", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );

    expect(captureErrorMock).toHaveBeenCalledTimes(1);
    const reportedError = captureErrorMock.mock.calls[0]?.[0];
    expect(reportedError).toBeInstanceOf(Error);
    expect((reportedError as Error).message).toBe("kaboom");
  });
});
