import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

async function loadPublicEnvModule() {
  vi.resetModules();
  return import("./public-env");
}

describe("getPublicSentryDsn (server/SSR — no window)", () => {
  it("is empty when neither PUBLIC_SENTRY_DSN nor VITE_SENTRY_DSN is set", async () => {
    vi.stubEnv("PUBLIC_SENTRY_DSN", "");
    vi.stubEnv("VITE_SENTRY_DSN", "");
    const { getPublicSentryDsn } = await loadPublicEnvModule();
    expect(getPublicSentryDsn()).toBe("");
  });

  it("prefers the runtime PUBLIC_SENTRY_DSN over the build-time VITE_SENTRY_DSN", async () => {
    vi.stubEnv("PUBLIC_SENTRY_DSN", "https://runtime@o1.ingest.sentry.io/1");
    vi.stubEnv("VITE_SENTRY_DSN", "https://buildtime@o1.ingest.sentry.io/2");
    const { getPublicSentryDsn } = await loadPublicEnvModule();
    expect(getPublicSentryDsn()).toBe("https://runtime@o1.ingest.sentry.io/1");
  });

  it("falls back to the build-time VITE_SENTRY_DSN when no runtime var is set", async () => {
    vi.stubEnv("PUBLIC_SENTRY_DSN", "");
    vi.stubEnv("VITE_SENTRY_DSN", "https://buildtime@o1.ingest.sentry.io/2");
    const { getPublicSentryDsn } = await loadPublicEnvModule();
    expect(getPublicSentryDsn()).toBe("https://buildtime@o1.ingest.sentry.io/2");
  });
});

describe("getPublicSentryDsn (browser)", () => {
  it("reads window.__TRUEGRIT_PUBLIC_ENV__ when present", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "");
    vi.stubGlobal("window", {
      __TRUEGRIT_PUBLIC_ENV__: { PUBLIC_SENTRY_DSN: "https://deployed@o1.ingest.sentry.io/9" },
    });
    const { getPublicSentryDsn } = await loadPublicEnvModule();
    expect(getPublicSentryDsn()).toBe("https://deployed@o1.ingest.sentry.io/9");
  });

  it("is empty when window is present but carries no DSN and none was baked in at build time", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "");
    vi.stubGlobal("window", { __TRUEGRIT_PUBLIC_ENV__: {} });
    const { getPublicSentryDsn } = await loadPublicEnvModule();
    expect(getPublicSentryDsn()).toBe("");
  });
});
