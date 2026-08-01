import { describe, expect, it } from "vitest";
import {
  actionColor,
  formatVertical,
  profileStatusColor,
  severityColor,
  statusColor,
  truncateId,
} from "../lib/format";

describe("formatVertical", () => {
  it("maps known verticals", () => {
    expect(formatVertical("sba_7a")).toBe("SBA 7(a)");
    expect(formatVertical("cre_acquisition")).toBe("CRE Acquisition");
    expect(formatVertical("specialty_mortgage_bank_statement")).toBe(
      "Bank Statement Mortgage"
    );
  });
});

describe("statusColor", () => {
  it("returns distinct classes", () => {
    expect(statusColor("completed")).toContain("emerald");
    expect(statusColor("failed")).toContain("red");
    expect(statusColor("queued")).toContain("amber");
  });
});

describe("actionColor", () => {
  it("handles null as slate", () => {
    expect(actionColor(null)).toContain("slate");
    expect(actionColor("approve")).toContain("emerald");
    expect(actionColor("decline")).toContain("red");
  });
});

describe("severityColor / profileStatusColor", () => {
  it("maps severities and profile statuses", () => {
    expect(severityColor("high")).toContain("red");
    expect(severityColor("medium")).toContain("amber");
    expect(profileStatusColor("flagged")).toContain("red");
    expect(profileStatusColor("corroborated")).toContain("emerald");
  });
});

describe("truncateId", () => {
  it("shortens ids", () => {
    expect(truncateId("abcdefghijklmnop")).toBe("abcdefgh…");
  });
});
