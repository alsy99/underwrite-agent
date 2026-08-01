import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SetupBanner } from "../components/SetupBanner";

describe("SetupBanner", () => {
  it("hides in DEV mode", () => {
    vi.stubEnv("DEV", true);
    const { container } = render(<SetupBanner />);
    // isBackendConfigured uses import.meta.env.DEV — true under vitest by default
    expect(container).toBeEmptyDOMElement();
  });
});

describe("StatusBadge", () => {
  it("renders status label", async () => {
    const { StatusBadge } = await import("../components/StatusBadge");
    render(<StatusBadge status="completed" />);
    expect(screen.getByText(/completed/i)).toBeInTheDocument();
  });
});
