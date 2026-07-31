import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getInventoryValuation, getLowStockCount, getStock } from "./inventory";
import { setToken, clearToken } from "../auth/token";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
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

describe("getStock", () => {
  it("calls GET /inventory/stock with exactly the real contract's query params", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await getStock({ category: "Decorations", lowStock: true, search: "glass", limit: 50, offset: 10 });

    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.pathname).toBe("/inventory/stock");
    expect(calledUrl.searchParams.get("category")).toBe("Decorations");
    expect(calledUrl.searchParams.get("low_stock")).toBe("true");
    expect(calledUrl.searchParams.get("search")).toBe("glass");
    expect(calledUrl.searchParams.get("limit")).toBe("50");
    expect(calledUrl.searchParams.get("offset")).toBe("10");
  });

  it("parses a real-shaped StockItem response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse([
          {
            _provenance: { quantity_on_hand: "derived" },
            _derivation_ref: {},
            sku: "85048",
            description: "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
            category: "Decorations",
            quantity_on_hand: 96,
            reorder_point: 120,
            safety_stock: 40,
            as_of_date: "2011-12-09",
            is_low_stock: true,
          },
        ]),
      ),
    );

    const items = await getStock({ limit: 100, offset: 0 });
    expect(items).toHaveLength(1);
    expect(items[0].sku).toBe("85048");
    expect(items[0].is_low_stock).toBe(true);
  });
});

describe("getLowStockCount", () => {
  it("reports an exact count when the response is under the API's page-size cap", async () => {
    const items = Array.from({ length: 204 }, (_, i) => ({
      _provenance: {},
      _derivation_ref: {},
      sku: `sku-${i}`,
      description: null,
      category: null,
      quantity_on_hand: 1,
      reorder_point: 10,
      safety_stock: 5,
      as_of_date: "2011-12-09",
      is_low_stock: true,
    }));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(items)));

    const result = await getLowStockCount();

    expect(result).toEqual({ count: 204, isLowerBound: false });
  });

  it("flags the count as a lower bound when the response hits the 1000-row cap exactly", async () => {
    const items = Array.from({ length: 1000 }, (_, i) => ({
      _provenance: {},
      _derivation_ref: {},
      sku: `sku-${i}`,
      description: null,
      category: null,
      quantity_on_hand: 1,
      reorder_point: 10,
      safety_stock: 5,
      as_of_date: "2011-12-09",
      is_low_stock: true,
    }));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(items)));

    const result = await getLowStockCount();

    expect(result).toEqual({ count: 1000, isLowerBound: true });
  });

  it("requests the API's maximum page size (1000) so undercounting is as unlikely as this endpoint allows", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await getLowStockCount();

    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.searchParams.get("limit")).toBe("1000");
  });
});

describe("getInventoryValuation", () => {
  it("parses a real-shaped InventoryValuation response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({
          _provenance: { total_inventory_value: "derived" },
          _derivation_ref: {},
          by_category: [],
          total_quantity_on_hand: 128400,
          total_inventory_value: 297512.1,
        }),
      ),
    );

    const result = await getInventoryValuation();
    expect(result.total_inventory_value).toBe(297512.1);
  });
});
