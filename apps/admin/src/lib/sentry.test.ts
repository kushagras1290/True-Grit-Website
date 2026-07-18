import { afterEach, describe, expect, it, vi } from "vitest";

const sentryInitMock = vi.fn();
const captureExceptionMock = vi.fn();

vi.mock("@sentry/react", () => ({
  init: sentryInitMock,
  captureException: captureExceptionMock,
}));

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.resetModules();
  sentryInitMock.mockClear();
  captureExceptionMock.mockClear();
});

async function loadSentryModule() {
  vi.resetModules();
  return import("./sentry");
}

describe("admin Sentry integration (VITE_SENTRY_DSN unset)", () => {
  it("is reported as disabled", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "");
    const { sentryEnabled } = await loadSentryModule();
    expect(sentryEnabled).toBe(false);
  });

  it("initSentry never calls Sentry.init", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "");
    const { initSentry } = await loadSentryModule();
    initSentry();
    expect(sentryInitMock).not.toHaveBeenCalled();
  });

  it("captureError never calls Sentry.captureException", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "");
    const { captureError } = await loadSentryModule();
    captureError(new Error("boom"));
    expect(captureExceptionMock).not.toHaveBeenCalled();
  });
});

describe("admin Sentry integration (VITE_SENTRY_DSN set)", () => {
  it("is reported as enabled", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "https://public@o1.ingest.sentry.io/1");
    const { sentryEnabled } = await loadSentryModule();
    expect(sentryEnabled).toBe(true);
  });

  it("initSentry calls Sentry.init with the configured dsn, once", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "https://public@o1.ingest.sentry.io/1");
    const { initSentry } = await loadSentryModule();
    initSentry();
    initSentry();
    expect(sentryInitMock).toHaveBeenCalledTimes(1);
    expect(sentryInitMock).toHaveBeenCalledWith(
      expect.objectContaining({ dsn: "https://public@o1.ingest.sentry.io/1" }),
    );
  });

  it("captureError forwards to Sentry.captureException", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "https://public@o1.ingest.sentry.io/1");
    const { captureError } = await loadSentryModule();
    const error = new Error("boom");
    captureError(error, { componentStack: "at Foo" });
    expect(captureExceptionMock).toHaveBeenCalledWith(error, {
      extra: { componentStack: "at Foo" },
    });
  });
});
