import type { AuditEvent, CaseListItem, CaseResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "/api";
const API_KEY = import.meta.env.VITE_API_KEY || "dev-api-key-change-me";
const assetBase = import.meta.env.BASE_URL;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Authorization") && path !== "/health") {
    headers.set("Authorization", `Bearer ${API_KEY}`);
  }
  if (API_BASE.includes("ngrok")) {
    headers.set("ngrok-skip-browser-warning", "true");
  }
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function healthCheck(): Promise<{ status: string }> {
  return request("/health");
}

export async function listCases(tenantId = "default"): Promise<CaseListItem[]> {
  return request(`/v1/cases?tenant_id=${tenantId}&limit=100`);
}

export async function getCase(caseId: string): Promise<CaseResponse> {
  return request(`/v1/cases/${caseId}`);
}

export async function getAudit(caseId: string): Promise<AuditEvent[]> {
  return request(`/v1/cases/${caseId}/audit`);
}

export async function createCase(
  vertical: string,
  metadata: Record<string, string>,
  files: File[]
): Promise<CaseResponse> {
  const form = new FormData();
  form.append("vertical", vertical);
  form.append("tenant_id", "default");
  form.append("metadata", JSON.stringify(metadata));
  files.forEach((f) => form.append("documents", f));
  return request("/v1/cases", { method: "POST", body: form });
}

export async function uploadPolicySba(): Promise<{ id: string }> {
  const content = await fetch(`${assetBase}fixtures/sba_policy_seed.md`).then((r) =>
    r.text()
  );
  return request("/v1/tenants/default/policies/json", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: "SBA Policy Seed",
      policy_version: "2026.05.1",
      filename: "sba_policy_seed.md",
      content,
    }),
  });
}
