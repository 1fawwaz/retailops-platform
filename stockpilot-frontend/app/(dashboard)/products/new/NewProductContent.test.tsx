import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NewProductContent } from "./NewProductContent";
import { setToken, clearToken } from "../../../../lib/auth/token";
import { setCachedPermissions, clearCachedPermissions } from "../../../../lib/auth/permissionsCache";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NewProductContent />
    </QueryClientProvider>,
  );
}

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

describe("NewProductContent", () => {
  it("shows a permission-denied empty state when the user lacks products:create", () => {
    renderWithClient();

    expect(
      screen.getByText("You don't have permission to create products"),
    ).toBeInTheDocument();
  });

  it("submits the form and redirects to the new product's detail page", async () => {
    const user = userEvent.setup();
    setCachedPermissions(["admin"], ["products:create"]);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        const path = new URL(url).pathname;
        if (path === "/categories") return Promise.resolve(jsonResponse([]));
        if (path === "/brands") return Promise.resolve(jsonResponse([]));
        if (path === "/suppliers") return Promise.resolve(jsonResponse([]));
        if (path === "/products" && init?.method === "POST") {
          return Promise.resolve(
            jsonResponse(
              {
                _provenance: {},
                _derivation_ref: {},
                sku: "SKU-NEW",
                description: null,
                category_id: null,
                supplier_id: null,
                brand_id: null,
                unit_cost: null,
                sale_price: null,
                reorder_point: null,
                safety_stock: null,
                created_at: "2026-01-01T00:00:00Z",
              },
              201,
            ),
          );
        }
        throw new Error(`Unexpected fetch to ${path}`);
      }),
    );

    renderWithClient();
    await user.type(screen.getByLabelText("SKU"), "SKU-NEW");
    await user.click(screen.getByRole("button", { name: "Create product" }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/products/SKU-NEW"));
  });

  it("shows a business-rule error when the SKU already exists", async () => {
    const user = userEvent.setup();
    setCachedPermissions(["admin"], ["products:create"]);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        const path = new URL(url).pathname;
        if (path === "/categories") return Promise.resolve(jsonResponse([]));
        if (path === "/brands") return Promise.resolve(jsonResponse([]));
        if (path === "/suppliers") return Promise.resolve(jsonResponse([]));
        if (path === "/products" && init?.method === "POST") {
          return Promise.resolve(jsonResponse({ detail: "Product 'SKU-1' already exists" }, 409));
        }
        throw new Error(`Unexpected fetch to ${path}`);
      }),
    );

    renderWithClient();
    await user.type(screen.getByLabelText("SKU"), "SKU-1");
    await user.click(screen.getByRole("button", { name: "Create product" }));

    expect(await screen.findByText("Product 'SKU-1' already exists")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
