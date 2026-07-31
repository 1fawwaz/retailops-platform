import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InventoryContent } from "./InventoryContent";
import { setToken, clearToken } from "../../../lib/auth/token";

const push = vi.fn();
let searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/inventory",
  useSearchParams: () => searchParams,
}));

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

function stockItem(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    _provenance: {},
    _derivation_ref: {},
    sku: "85048",
    description: "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
    category: "Decorations",
    quantity_on_hand: 96,
    reorder_point: 120,
    safety_stock: 40,
    as_of_date: "2011-12-09",
    is_low_stock: true,
    ...overrides,
  };
}

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <InventoryContent />
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
  );
});

afterEach(() => {
  clearToken();
  vi.unstubAllGlobals();
});

describe("InventoryContent", () => {
  it("renders fetched rows in the table", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([stockItem()])));

    renderWithClient();

    expect(await screen.findByText("85048")).toBeInTheDocument();
    expect(screen.getByText("Low stock")).toBeInTheDocument();
  });

  it("shows the genuinely-empty state when the query has no filters and returns nothing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    renderWithClient();

    expect(await screen.findByText("No inventory yet")).toBeInTheDocument();
  });

  it("shows the filtered-empty state (distinct wording) when a filter is active and returns nothing", async () => {
    searchParams = new URLSearchParams({ search: "nonexistent" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    renderWithClient();

    expect(await screen.findByText("No items match these filters")).toBeInTheDocument();
  });

  it("pushes search and category into the URL when the filter form is submitted", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([stockItem()])));

    renderWithClient();
    await screen.findByText("85048");

    await user.type(screen.getByLabelText("Search"), "glass");
    await user.type(screen.getByLabelText("Category"), "Decorations");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    expect(push).toHaveBeenCalledWith("/inventory?search=glass&category=Decorations");
  });

  it("requests the real /inventory/stock query params for search/category/low_stock", async () => {
    searchParams = new URLSearchParams({ search: "glass", category: "Decorations", low_stock: "true" });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    renderWithClient();

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const calledUrl = new URL(fetchMock.mock.calls[0][0] as string);
    expect(calledUrl.searchParams.get("search")).toBe("glass");
    expect(calledUrl.searchParams.get("category")).toBe("Decorations");
    expect(calledUrl.searchParams.get("low_stock")).toBe("true");
  });

  it("shows an error message without crashing when the endpoint fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("error", { status: 500 })));

    renderWithClient();

    expect(
      await screen.findByText("Something went wrong on our end. Please try again in a moment."),
    ).toBeInTheDocument();
  });

  it("discloses that warehouse/location filtering, supplier filtering, and bulk actions are unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    renderWithClient();

    expect(
      await screen.findByText(/Warehouse\/location filtering, supplier filtering, and bulk actions/),
    ).toBeInTheDocument();
  });
});
