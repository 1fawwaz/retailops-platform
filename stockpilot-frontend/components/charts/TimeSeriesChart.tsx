"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// docs/DESIGN-SPEC.md §3 color rule 5: "Chart series use a neutral
// sequence derived from the gray ramp plus accent as the single
// highlight. Forecast bands are gray, never colored." This wrapper is
// the one place a chart color is chosen -- a resource page passes data,
// never a color.

export interface TimeSeriesPoint {
  label: string;
  value: number;
}

export interface TimeSeriesChartProps {
  data: TimeSeriesPoint[];
  /** True renders the line in the neutral gray (e.g. a forecast band), false uses the single accent highlight. */
  neutral?: boolean;
  height?: number;
}

export function TimeSeriesChart({ data, neutral = false, height = 240 }: TimeSeriesChartProps) {
  const strokeColor = neutral ? "var(--color-text-low)" : "var(--color-accent)";

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--color-hairline)" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: "var(--color-text-mid)", fontSize: 11 }}
          axisLine={{ stroke: "var(--color-hairline)" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "var(--color-text-mid)", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          width={48}
        />
        <Tooltip
          contentStyle={{
            background: "var(--color-raised)",
            border: "1px solid var(--color-hairline)",
            borderRadius: 6,
            fontSize: 13,
          }}
        />
        <Line
          type="monotone"
          dataKey="value"
          stroke={strokeColor}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
