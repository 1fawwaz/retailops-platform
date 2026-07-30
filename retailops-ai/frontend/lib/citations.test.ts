import { describe, expect, it } from "vitest";
import { buildCitationSegments, normalizeToken } from "@/lib/citations";
import type { CitationEntry } from "@/lib/types";

function citation(overrides: Partial<CitationEntry>): CitationEntry {
  return {
    token: "12",
    value: 12,
    tool_call_id: "call-1",
    tool_name: "get_low_stock",
    agent: "inventory",
    field_name: "quantity_on_hand",
    provenance: "derived",
    ...overrides,
  };
}

describe("normalizeToken", () => {
  it("strips currency symbols, thousands separators, and percent signs", () => {
    expect(normalizeToken("$2.15")).toBe(2.15);
    expect(normalizeToken("£47,000")).toBe(47000);
    expect(normalizeToken("15%")).toBe(15);
    expect(normalizeToken("-3.5")).toBe(-3.5);
  });

  it("returns null for a non-numeric string", () => {
    expect(normalizeToken("SKU")).toBeNull();
  });
});

describe("buildCitationSegments", () => {
  it("returns the whole text as one segment when there are no citations", () => {
    const segments = buildCitationSegments("No numbers here.", []);
    expect(segments).toEqual([{ type: "text", value: "No numbers here." }]);
  });

  it("wraps a matching number in a citation segment, splitting the surrounding text", () => {
    const citations = [citation({ value: 2.15 })];
    const segments = buildCitationSegments("The unit cost is $2.15 today.", citations);

    expect(segments).toEqual([
      { type: "text", value: "The unit cost is " },
      { type: "citation", token: "$2.15", citation: citations[0] },
      { type: "text", value: " today." },
    ]);
  });

  it("chips every occurrence of a repeated value, not just the first", () => {
    const citations = [citation({ value: 2.15 })];
    const segments = buildCitationSegments("$2.15 and again $2.15.", citations);
    const citationSegments = segments.filter((s) => s.type === "citation");
    expect(citationSegments).toHaveLength(2);
  });

  it("leaves a MISSING SOURCE citation (tool_call_id null) chippable too", () => {
    const citations = [citation({ value: 47000, tool_call_id: null, tool_name: null, agent: null })];
    const segments = buildCitationSegments("Revenue at risk is $47,000.", citations);
    const citationSegment = segments.find((s) => s.type === "citation");
    expect(citationSegment?.type).toBe("citation");
    expect(citationSegment && citationSegment.type === "citation" && citationSegment.citation.tool_call_id).toBeNull();
  });

  it("renders a numeric-looking substring with no matching citation as plain text", () => {
    const segments = buildCitationSegments("See item #7 for details.", [citation({ value: 12 })]);
    expect(segments).toEqual([{ type: "text", value: "See item #7 for details." }]);
  });
});
