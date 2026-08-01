import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardContent } from "./DashboardContent";
import { setToken, clearToken } from "../../../lib/auth/token";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function renderWithQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
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

// BUILD.md Stage 1's own required test: "Integration: dashboard renders
// correctly across loading/empty/populated/error states for each panel."
describe("DashboardContent", () => {
  it("renders populated KPI cards from real-shaped endpoint responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        const path = new URL(url).pathname;
        if (path === "/analytics/revenue") {
          return Promise.resolve(
            jsonResponse([
              { _provenance: {}, _derivation_ref: {}, period: "2011-10", revenue: 700000, units: 400000 },
              { _provenance: {}, _derivation_ref: {}, period: "2011-11", revenue: 801102.97, units: 445513 },
            ]),
          );
        }
        if (path === "/inventory/valuation") {
          return Promise.resolve(
            jsonResponse({
              _provenance: {},
              _derivation_ref: {},
              by_category: [],
              total_quantity_on_hand: 128400,
              total_inventory_value: 297512.1,
            }),
          );
        }
        if (path === "/inventory/low-stock") {
          return Promise.resolve(jsonResponse([]));
        }
        throw new Error(`Unexpected fetch to ${path}`);
      }),
    );

    renderWithQueryClient(<DashboardContent />);

    expect(await screen.findByText("£801,103")).toBeInTheDocument();
    expect(await screen.findByText("+14.4% vs. prior month")).toBeInTheDocument();
    expect(await screen.findByText("£297,512")).toBeInTheDocument();
    expect(await screen.findByText("0")).toBeInTheDocument();
  });

  it("shows a specific error message on a KPI card when its endpoint fails, without breaking the others", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        const path = new URL(url).pathname;
        if (path === "/analytics/revenue") {
          return Promise.resolve(new Response("Server error", { status: 500 }));
        }
        if (path === "/inventory/valuation") {
          return Promise.resolve(
            jsonResponse({
              _provenance: {},
              _derivation_ref: {},
              by_category: [],
              total_quantity_on_hand: 1,
              total_inventory_value: 10,
            }),
          );
        }
        if (path === "/inventory/low-stock") {
          return Promise.resolve(jsonResponse([]));
        }
        throw new Error(`Unexpected fetch to ${path}`);
      }),
    );

    renderWithQueryClient(<DashboardContent />);

    await waitFor(() =>
      expect(
        screen.getByText("Something went wrong on our end. Please try again in a moment."),
      ).toBeInTheDocument(),
    );
    // The other two cards still render despite Revenue's failure.
    expect(await screen.findByText("£10")).toBeInTheDocument();
  });

  it("always discloses the missing Purchase Orders / activity feed data, rather than omitting it silently", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    renderWithQueryClient(<DashboardContent />);

    expect(screen.getByText(/StockPilot Core has no Purchase Orders or Sales API/)).toBeInTheDocument();
  });
});
