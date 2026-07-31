import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getForecast } from "./forecast";
import { setToken, clearToken } from "../auth/token";

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

describe("getForecast", () => {
  it("POSTs the real ForecastRequest shape (skus array + horizon_days)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getForecast("85048", 14);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new URL(url).pathname).toBe("/forecast/demand");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ skus: ["85048"], horizon_days: 14 });
  });

  it("returns the matching SkuForecast when the response includes it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            {
              _provenance: {},
              _derivation_ref: {},
              sku: "85048",
              predicted_daily_demand: 14.61,
              confidence_interval_lower: 0,
              confidence_interval_upper: 97.19,
              model_used: "moving_average",
              training_window_start: "2009-12-01",
              training_window_end: "2011-12-09",
              data_quality: "ok",
            },
          ]),
          { status: 200 },
        ),
      ),
    );

    const result = await getForecast("85048", 14);
    expect(result?.predicted_daily_demand).toBe(14.61);
  });

  it("returns null when the response doesn't include the requested SKU", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([]), { status: 200 })));

    const result = await getForecast("unknown-sku", 14);
    expect(result).toBeNull();
  });
});
