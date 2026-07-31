import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getRevenue } from "./analytics";
import { setToken, clearToken } from "../auth/token";

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

beforeEach(() => {
  setToken(
    `${btoa(JSON.stringify({ alg: "HS256" }))}.${btoa(
      JSON.stringify({ sub: "u@example.com", exp: 9999999999 }),
    )}.sig`,
  );
});

afterEach(() => {
  clearToken();
  vi.unstubAllGlobals();
});

describe("getRevenue", () => {
  it("calls GET /analytics/revenue with the real contract's group_by/date params", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await getRevenue({ groupBy: "month", startDate: "2011-01-01", endDate: "2011-12-09" });

    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.pathname).toBe("/analytics/revenue");
    expect(calledUrl.searchParams.get("group_by")).toBe("month");
    expect(calledUrl.searchParams.get("start_date")).toBe("2011-01-01");
    expect(calledUrl.searchParams.get("end_date")).toBe("2011-12-09");
  });

  it("parses a real-shaped RevenuePeriod array", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse([
          {
            _provenance: { revenue: "derived", units: "derived" },
            _derivation_ref: {},
            period: "2011-11",
            revenue: 801102.97,
            units: 445513,
          },
        ]),
      ),
    );

    const result = await getRevenue({ groupBy: "month" });
    expect(result).toHaveLength(1);
    expect(result[0].period).toBe("2011-11");
    expect(result[0].revenue).toBe(801102.97);
  });
});
