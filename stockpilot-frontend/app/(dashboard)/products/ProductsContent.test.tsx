import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProductsContent } from "./ProductsContent";
import { setToken, clearToken } from "../../../lib/auth/token";
import { setCachedPermissions, clearCachedPermissions } from "../../../lib/auth/permissionsCache";

const push = vi.fn();
let searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/products",
  useSearchParams: () => searchParams,
}));

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

function product(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    _provenance: {},
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
    ...overrides,
  };
}

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ProductsContent />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  push.mockClear();
  searchParams = new URLSearchParams();
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

describe("ProductsContent", () => {
  it("renders fetched rows in the table", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([product()])));

    renderWithClient();

    expect(await screen.findByText("85048")).toBeInTheDocument();
    expect(screen.getByText("£4.99")).toBeInTheDocument();
  });

  it("shows the genuinely-empty state when there are no filters and no products", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    renderWithClient();

    expect(await screen.findByText("No products yet")).toBeInTheDocument();
  });

  it("shows the filtered-empty state (distinct wording) when a filter is active and returns nothing", async () => {
    searchParams = new URLSearchParams({ search: "nonexistent" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    renderWithClient();

    expect(await screen.findByText("No products match these filters")).toBeInTheDocument();
  });

  it("pushes search and category into the URL when the filter form is submitted", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([product()])));

    renderWithClient();
    await screen.findByText("85048");

    await user.type(screen.getByLabelText("Search"), "glass");
    await user.type(screen.getByLabelText("Category"), "Decorations");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    expect(push).toHaveBeenCalledWith("/products?search=glass&category=Decorations");
  });

  it("requests the real GET /products query params for search/category", async () => {
    searchParams = new URLSearchParams({ search: "glass", category: "Decorations" });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient();

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.searchParams.get("search")).toBe("glass");
    expect(calledUrl.searchParams.get("category")).toBe("Decorations");
  });

  it("shows an error message without crashing when the endpoint fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("error", { status: 500 })));

    renderWithClient();

    expect(
      await screen.findByText("Something went wrong on our end. Please try again in a moment."),
    ).toBeInTheDocument();
  });

  it("hides the New product action when the user lacks products:create", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([product()])));

    renderWithClient();
    await screen.findByText("85048");

    expect(screen.queryByRole("link", { name: "New product" })).not.toBeInTheDocument();
  });

  it("shows the New product action when the user has products:create", async () => {
    setCachedPermissions(["admin"], ["products:create"]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([product()])));

    renderWithClient();
    await screen.findByText("85048");

    expect(screen.getByRole("link", { name: "New product" })).toBeInTheDocument();
  });

  it("discloses that product images are unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    renderWithClient();

    expect(await screen.findByText(/Product images are not available/)).toBeInTheDocument();
  });
});
