import { beforeEach, describe, expect, it, vi } from "vitest";

describe("api client", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubEnv("VITE_API_URL", "/api");
    vi.stubEnv("VITE_API_KEY", "test-key");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const headers = new Headers(init?.headers);
        return {
          ok: true,
          status: 200,
          json: async () => {
            if (String(url).includes("/health")) return { status: "ok" };
            if (String(url).includes("/v1/cases/") && !String(url).includes("?")) {
              return { case_id: "c1", status: "completed" };
            }
            return [{ case_id: "c1", status: "completed" }];
          },
          text: async () => "",
        } as Response;
      })
    );
  });

  it("sends bearer token on listCases", async () => {
    const api = await import("./api");
    await api.listCases();
    expect(fetch).toHaveBeenCalled();
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer test-key");
  });

  it("healthCheck hits /health", async () => {
    const api = await import("./api");
    const out = await api.healthCheck();
    expect(out.status).toBe("ok");
    expect(String((fetch as ReturnType<typeof vi.fn>).mock.calls[0][0])).toContain(
      "/health"
    );
  });

  it("createCase posts FormData", async () => {
    const api = await import("./api");
    const file = new File(["hello"], "form_1919.txt", { type: "text/plain" });
    await api.createCase("sba_7a", { business_name: "Acme" }, [file]);
    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls.at(-1)!;
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    const form = init.body as FormData;
    expect(form.get("vertical")).toBe("sba_7a");
    expect(form.get("metadata")).toContain("Acme");
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: false,
        status: 500,
        statusText: "Server Error",
        text: async () => "boom",
      }))
    );
    const api = await import("./api");
    await expect(api.listCases()).rejects.toThrow("boom");
  });
});
