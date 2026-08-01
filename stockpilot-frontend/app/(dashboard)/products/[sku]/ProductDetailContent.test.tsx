import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProductDetailContent } from "./ProductDetailContent";
import { setToken, clearToken } from "../../../../lib/auth/token";
import { setCachedPermissions, clearCachedPermissions } from "../../../../lib/auth/permissionsCache";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function mockRoutes(overrides: {
  product?: Response;
  categories?: Response;
  brands?: Response;
  supplier?: Response;
  history?: Response;
  deleteStatus?: number;
}) {
  const deleteStatus = overrides.deleteStatus ?? 204;
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      const path = new URL(url).pathname;
      if (init?.method === "DELETE" && path.startsWith("/products/")) {
        return Promise.resolve(new Response(null, { status: deleteStatus }));
      }
      if (path === "/products/85048/history") return Promise.resolve(overrides.history);
      if (path.startsWith("/products/")) return Promise.resolve(overrides.product);
      if (path === "/categories") return Promise.resolve(overrides.categories);
      if (path === "/brands") return Promise.resolve(overrides.brands);
      if (path.startsWith("/suppliers/")) return Promise.resolve(overrides.supplier);
      throw new Error(`Unexpected fetch to ${path}`);
    }),
  );
}

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ProductDetailContent sku="85048" />
    </QueryClientProvider>,
  );
}

const PRODUCT = {
  _provenance: { unit_cost: "derived", sale_price: "observed" },
  _derivation_ref: {},
  sku: "85048",
  description: "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
  category_id: 3,
  supplier_id: 7,
  brand_id: null,
  unit_cost: 2.15,
  sale_price: 4.99,
  reorder_point: 120,
  safety_stock: 40,
  created_at: "2026-01-01T00:00:00Z",
  quantity_on_hand: 96,
  movement_history: [],
};

beforeEach(() => {
  push.mockClear();
  setToken(
    `${btoa(JSON.stringify({ alg: "HS256" }))}.${btoa(
      JSON.stringify({ sub: "u@example.com", exp: 9999999999 }),
    )}.sig`,
    "test-refresh-token",
  );
});

afterEach(() => {
  clearToken();
  clearCachedPermissions();
  vi.unstubAllGlobals();
});

describe("ProductDetailContent", () => {
  it("renders pricing, category, and history", async () => {
    mockRoutes({
      product: jsonResponse(PRODUCT),
      categories: jsonResponse([{ id: 3, name: "Decorations", created_at: "2026-01-01T00:00:00Z" }]),
      brands: jsonResponse([]),
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
      history: jsonResponse([
        {
          field_name: "unit_cost",
          old_value: "1.0",
          new_value: "2.15",
          changed_by_user_id: 1,
          changed_at: "2026-01-02T00:00:00Z",
        },
      ]),
    });

    renderWithClient();

    expect(await screen.findByText("£4.99")).toBeInTheDocument();
    expect(screen.getByText("Decorations")).toBeInTheDocument();
    expect(await screen.findByText("unit_cost")).toBeInTheDocument();
    expect(await screen.findByText(/Acme Wholesale Co/)).toBeInTheDocument();
  });

  it("shows a not-found empty state for a nonexistent SKU", async () => {
    mockRoutes({
      product: jsonResponse({ detail: "Not found" }, 404),
      categories: jsonResponse([]),
      brands: jsonResponse([]),
      history: jsonResponse([]),
    });

    renderWithClient();

    expect(await screen.findByText("Product not found")).toBeInTheDocument();
  });

  it("hides Edit/Delete when the user lacks the permissions", async () => {
    mockRoutes({
      product: jsonResponse(PRODUCT),
      categories: jsonResponse([]),
      brands: jsonResponse([]),
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
      history: jsonResponse([]),
    });

    renderWithClient();
    await screen.findByText("15CM CHRISTMAS GLASS BALL 20 LIGHTS");

    expect(screen.queryByRole("link", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("deletes the product and redirects to the list after confirming", async () => {
    const user = userEvent.setup();
    setCachedPermissions(["admin"], ["products:update", "products:delete"]);
    mockRoutes({
      product: jsonResponse(PRODUCT),
      categories: jsonResponse([]),
      brands: jsonResponse([]),
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
      history: jsonResponse([]),
    });

    renderWithClient();
    await screen.findByText("15CM CHRISTMAS GLASS BALL 20 LIGHTS");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/products"));
  });

  it("shows a business-rule error and cancels the confirm state when delete is blocked", async () => {
    const user = userEvent.setup();
    setCachedPermissions(["admin"], ["products:update", "products:delete"]);
    mockRoutes({
      product: jsonResponse(PRODUCT),
      categories: jsonResponse([]),
      brands: jsonResponse([]),
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
      history: jsonResponse([]),
      deleteStatus: 409,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        const path = new URL(url).pathname;
        if (init?.method === "DELETE") {
          return Promise.resolve(
            jsonResponse({ detail: "Cannot delete a product with open purchase order lines" }, 409),
          );
        }
        if (path === "/products/85048/history") return Promise.resolve(jsonResponse([]));
        if (path.startsWith("/products/")) return Promise.resolve(jsonResponse(PRODUCT));
        if (path === "/categories") return Promise.resolve(jsonResponse([]));
        if (path === "/brands") return Promise.resolve(jsonResponse([]));
        if (path.startsWith("/suppliers/")) {
          return Promise.resolve(
            jsonResponse({
              _provenance: {},
              _derivation_ref: {},
              id: 7,
              name: "Acme Wholesale Co",
              lead_time_days: 7,
              reliability_score: 0.92,
              created_at: "2026-01-01T00:00:00Z",
              skus: ["85048"],
            }),
          );
        }
        throw new Error(`Unexpected fetch to ${path}`);
      }),
    );

    renderWithClient();
    await screen.findByText("15CM CHRISTMAS GLASS BALL 20 LIGHTS");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(
      await screen.findByText("Cannot delete a product with open purchase order lines"),
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalledWith("/products");
  });
});
