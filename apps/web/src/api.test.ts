import { describe, expect, it } from "vitest";
import { formatMoney, formatPercent } from "./api";

describe("finance formatters", () => {
  it("formats integer paise as Indian rupees", () => {
    expect(formatMoney(12_345)).toContain("123.45");
  });

  it("formats decimal ratios as percentages", () => {
    expect(formatPercent(0.875)).toContain("87.5");
  });
});
