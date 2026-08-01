import { beforeEach, describe, expect, it, vi } from "vitest";

describe("auth", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  it("skips gate when no password configured", async () => {
    vi.stubEnv("VITE_UI_PASSWORD", "");
    vi.stubEnv("VITE_UI_PASSWORD_HASH", "");
    const auth = await import("./auth");
    expect(auth.isAuthRequired()).toBe(false);
    expect(auth.isAuthenticated()).toBe(true);
    expect(await auth.login("x")).toBe(true);
  });

  it("gates on plain password", async () => {
    vi.stubEnv("VITE_UI_PASSWORD", "demo-pass");
    vi.stubEnv("VITE_UI_PASSWORD_HASH", "");
    const auth = await import("./auth");
    expect(auth.isAuthRequired()).toBe(true);
    expect(auth.isAuthenticated()).toBe(false);
    expect(await auth.verifyPassword("wrong")).toBe(false);
    expect(await auth.login("demo-pass")).toBe(true);
    expect(auth.isAuthenticated()).toBe(true);
    auth.clearAuth();
    expect(auth.isAuthenticated()).toBe(false);
  });

  it("gates on sha256 hash", async () => {
    const data = new TextEncoder().encode("hashed-secret");
    const buf = await crypto.subtle.digest("SHA-256", data);
    const hex = Array.from(new Uint8Array(buf))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    vi.stubEnv("VITE_UI_PASSWORD", "");
    vi.stubEnv("VITE_UI_PASSWORD_HASH", hex);
    const auth = await import("./auth");
    expect(await auth.verifyPassword("hashed-secret")).toBe(true);
    expect(await auth.verifyPassword("nope")).toBe(false);
  });
});
