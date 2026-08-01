import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InventoryDetailContent } from "./InventoryDetailContent";
import { setToken, clearToken } from "../../../../lib/auth/token";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function renderWithClient(sku: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <InventoryDetailContent sku={sku} />
    </QueryClientProvider>,
  );
}

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

function mockRoutes(overrides: { product?: Response; stock?: Response; supplier?: Response; forecast?: Response }) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      const path = new URL(url).pathname;
      if (path.startsWith("/products/")) return Promise.resolve(overrides.product);
      if (path === "/inventory/stock") return Promise.resolve(overrides.stock);
      if (path.startsWith("/suppliers/")) return Promise.resolve(overrides.supplier);
      if (path === "/forecast/demand" && init?.method === "POST") return Promise.resolve(overrides.forecast);
      throw new Error(`Unexpected fetch to ${path}`);
    }),
  );
}

describe("InventoryDetailContent", () => {
  it("renders product, stock, supplier, and forecast data together", async () => {
    mockRoutes({
      product: jsonResponse({
        _provenance: { reorder_point: "derived", unit_cost: "derived" },
        _derivation_ref: {},
        sku: "85048",
        description: "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
        category_id: 3,
        supplier_id: 7,
        brand_id: null,
        unit_cost: 2.15,
        sale_price: null,
        reorder_point: 120,
        safety_stock: 40,
        created_at: "2026-01-01T00:00:00Z",
        quantity_on_hand: 96,
        movement_history: [],
      }),
      stock: jsonResponse([
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
      supplier: jsonResponse({
        _provenance: {},
        _derivation_ref: {},
        id: 7,
        name: "Acme Wholesale Co",
        lead_time_days: 7,
        reliability_score: 0.92,
        created_at: "2026-01-01T00:00:00Z",
        skus: ["85048"],
      }),
      forecast: jsonResponse([
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
    });

    renderWithClient("85048");

    expect(await screen.findByText("15CM CHRISTMAS GLASS BALL 20 LIGHTS")).toBeInTheDocument();
    expect(await screen.findByText("96")).toBeInTheDocument();
    expect(await screen.findByText(/Acme Wholesale Co/)).toBeInTheDocument();
    expect(await screen.findByText("14.6 units/day")).toBeInTheDocument();
  });

  it("shows a not-found empty state when the product doesn't exist", async () => {
    mockRoutes({
      product: new Response(JSON.stringify({ detail: "Not found" }), { status: 404 }),
      stock: jsonResponse([]),
      forecast: jsonResponse([]),
    });

    renderWithClient("does-not-exist");

    expect(await screen.findByText("Product not found")).toBeInTheDocument();
  });

  it("shows 'No supplier linked' rather than an error when supplier_id is null", async () => {
    mockRoutes({
      product: jsonResponse({
        _provenance: {},
        _derivation_ref: {},
        sku: "85048",
        description: "Widget",
        category_id: null,
        supplier_id: null,
        brand_id: null,
        unit_cost: null,
        sale_price: null,
        reorder_point: null,
        safety_stock: null,
        created_at: "2026-01-01T00:00:00Z",
        quantity_on_hand: null,
        movement_history: [],
      }),
      stock: jsonResponse([]),
      forecast: jsonResponse([]),
    });

    renderWithClient("85048");

    expect(await screen.findByText("No supplier linked.")).toBeInTheDocument();
  });
});
