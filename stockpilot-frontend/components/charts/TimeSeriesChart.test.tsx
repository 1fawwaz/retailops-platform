import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { TimeSeriesChart } from "./TimeSeriesChart";

// BUILD.md Stage 0's dummy resource, again -- a chart doesn't need a
// real revenue endpoint (Stage 1) to prove the wrapper renders and
// honors the neutral-vs-accent color rule from docs/DESIGN-SPEC.md §3.
const dummySeries = [
  { label: "Mon", value: 10 },
  { label: "Tue", value: 14 },
  { label: "Wed", value: 9 },
];

describe("TimeSeriesChart", () => {
  it("renders an SVG line chart without crashing", () => {
    const { container } = render(<TimeSeriesChart data={dummySeries} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
  });

  it("renders in a jsdom environment even with a forecast band's neutral styling", () => {
    const { container } = render(<TimeSeriesChart data={dummySeries} neutral />);
    expect(container.querySelector(".recharts-line")).toBeInTheDocument();
  });
});
