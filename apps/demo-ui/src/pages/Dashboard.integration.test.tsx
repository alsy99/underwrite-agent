import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Dashboard } from "./Dashboard";

vi.mock("../api", () => ({
  listCases: vi.fn(),
}));

import { listCases } from "../api";

describe("Dashboard integration", () => {
  beforeEach(() => {
    vi.mocked(listCases).mockReset();
  });

  it("renders cases from API", async () => {
    vi.mocked(listCases).mockResolvedValue([
      {
        case_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        status: "completed",
        vertical: "sba_7a",
        tenant_id: "default",
        created_at: "2026-07-01T12:00:00Z",
        completed_at: "2026-07-01T12:05:00Z",
        recommended_action: "review",
        findings_count: 2,
        contradictions_count: 1,
      },
    ]);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    expect(screen.getByText(/Investigation cases/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText(/SBA 7\(a\)/).length).toBeGreaterThan(0);
    });
    expect(listCases).toHaveBeenCalled();
  });

  it("shows error state", async () => {
    vi.mocked(listCases).mockRejectedValue(new Error("backend down"));
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/backend down/i)).toBeInTheDocument();
    });
  });
});
