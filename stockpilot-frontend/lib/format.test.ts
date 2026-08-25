import { describe, expect, it } from "vitest";
import {
  formatCurrency,
  formatCurrencyPrecise,
  formatInteger,
  formatPercentChange,
} from "./format";

describe("formatCurrency", () => {
  it("formats a positive value in INR with no decimals", () => {
    expect(formatCurrency(297512.1)).toBe("₹2,97,512");
  });

  it("formats zero", () => {
    expect(formatCurrency(0)).toBe("₹0");
  });
});

describe("formatCurrencyPrecise", () => {
  it("formats a per-unit price with exactly two decimals", () => {
    expect(formatCurrencyPrecise(4.99)).toBe("₹4.99");
  });

  it("does not round a sub-₹1 price down to ₹0", () => {
    expect(formatCurrencyPrecise(0.49)).toBe("₹0.49");
  });

  it("pads a whole-rupee value to two decimals", () => {
    expect(formatCurrencyPrecise(5)).toBe("₹5.00");
  });
});

describe("formatInteger", () => {
  it("adds thousands separators", () => {
    expect(formatInteger(128400)).toBe("1,28,400");
  });
});

describe("formatPercentChange", () => {
  it("formats a positive change with an explicit sign", () => {
    expect(formatPercentChange(110, 100)).toBe("+10.0%");
  });

  it("formats a negative change with an explicit sign", () => {
    expect(formatPercentChange(90, 100)).toBe("-10.0%");
  });

  it("returns null when the previous period was zero (undefined % change)", () => {
    expect(formatPercentChange(50, 0)).toBeNull();
  });
});
