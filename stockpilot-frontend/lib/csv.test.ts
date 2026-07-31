import { describe, expect, it } from "vitest";
import { toCsv } from "./csv";

describe("toCsv", () => {
  it("renders a header row and one row per item, in column order", () => {
    const csv = toCsv(
      [
        { sku: "85048", quantity_on_hand: 96 },
        { sku: "22841", quantity_on_hand: 12 },
      ],
      ["sku", "quantity_on_hand"],
    );
    expect(csv).toBe("sku,quantity_on_hand\n85048,96\n22841,12");
  });

  it("quotes and escapes values containing commas, quotes, or newlines", () => {
    const csv = toCsv([{ description: 'Says "hello", world\nline two' }], ["description"]);
    expect(csv).toBe('description\n"Says ""hello"", world\nline two"');
  });

  it("renders null/undefined as an empty cell, not the literal string", () => {
    const csv = toCsv([{ description: null }], ["description"]);
    expect(csv).toBe("description\n");
  });
});
