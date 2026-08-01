import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getProduct } from "./products";
import { setToken, clearToken } from "../auth/token";

beforeEach(() => {
  setToken(
    `${btoa(JSON.stringify({ alg: "HS256" }))}.${btoa(
      JSON.stringify({ sub: "u@example.com", exp: 9999999999 }),
    )}.sig`,
    "test-refresh-token",
  );
});

afterEach(() => {
  clearToken();
  vi.unstubAllGlobals();
});

describe("getProduct", () => {
  it("calls GET /products/{sku}, URL-encoding the SKU", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      _provenance: {},
      _derivation_ref: {},
      sku: "AB 123",
      description: null,
      category_id: null,
      supplier_id: 7,
      brand_id: null,
      unit_cost: 2.15,
      sale_price: null,
      reorder_point: 120,
      safety_stock: 40,
      created_at: "2026-01-01T00:00:00Z",
      quantity_on_hand: 96,
      movement_history: [],
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getProduct("AB 123");

    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.pathname).toBe("/products/AB%20123");
    expect(result.supplier_id).toBe(7);
  });
});
