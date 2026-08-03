import { afterEach, describe, expect, it, vi } from "vitest";

function unauthorizedResponse() {
  return new Response(JSON.stringify({ error: { message: "Unauthorized" } }), {
    status: 401,
    headers: { "content-type": "application/json" },
  });
}

async function loadLiveApiClient() {
  vi.resetModules();
  vi.stubEnv("VITE_API_URL", "https://api.test");
  return import("./api");
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("admin API auth expiry events", () => {
  it("emits an auth-expired event when a protected API call returns 401", async () => {
    const { ADMIN_AUTH_EXPIRED_EVENT, api } = await loadLiveApiClient();
    const listener = vi.fn();
    window.addEventListener(ADMIN_AUTH_EXPIRED_EVENT, listener);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(unauthorizedResponse()));

    await expect(api.products()).rejects.toMatchObject({ status: 401 });

    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(ADMIN_AUTH_EXPIRED_EVENT, listener);
  }, 15_000);

  it("does not emit for the session probe or login endpoint", async () => {
    const { ADMIN_AUTH_EXPIRED_EVENT, api } = await loadLiveApiClient();
    const listener = vi.fn();
    window.addEventListener(ADMIN_AUTH_EXPIRED_EVENT, listener);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(unauthorizedResponse()));

    await expect(api.me()).rejects.toMatchObject({ status: 401 });
    await expect(api.login("nobody@example.com", "wrong-password")).rejects.toMatchObject({
      status: 401,
    });

    expect(listener).not.toHaveBeenCalled();
    window.removeEventListener(ADMIN_AUTH_EXPIRED_EVENT, listener);
  });
});
