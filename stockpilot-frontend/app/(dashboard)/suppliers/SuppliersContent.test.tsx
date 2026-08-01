import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SuppliersContent } from "./SuppliersContent";
import { setToken, clearToken } from "../../../lib/auth/token";
import { setCachedPermissions, clearCachedPermissions } from "../../../lib/auth/permissionsCache";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

function supplier(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    _provenance: {},
    _derivation_ref: {},
    id: 7,
    name: "Acme Wholesale Co",
    lead_time_days: 7,
    reliability_score: 0.92,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SuppliersContent />
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

describe("SuppliersContent", () => {
  it("renders fetched rows in the table", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([supplier()])));

    renderWithClient();

    expect(await screen.findByText("Acme Wholesale Co")).toBeInTheDocument();
    expect(screen.getByText("0.92")).toBeInTheDocument();
  });

  it("shows the empty state when there are no suppliers", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));

    renderWithClient();

    expect(await screen.findByText("No suppliers yet")).toBeInTheDocument();
  });

  it("shows an error message without crashing when the endpoint fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("error", { status: 500 })));

    renderWithClient();

    expect(
      await screen.findByText("Something went wrong on our end. Please try again in a moment."),
    ).toBeInTheDocument();
  });

  it("hides the New supplier action when the user lacks suppliers:create", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([supplier()])));

    renderWithClient();
    await screen.findByText("Acme Wholesale Co");

    expect(screen.queryByRole("link", { name: "New supplier" })).not.toBeInTheDocument();
  });

  it("shows the New supplier action when the user has suppliers:create", async () => {
    setCachedPermissions(["admin"], ["suppliers:create"]);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([supplier()])));

    renderWithClient();
    await screen.findByText("Acme Wholesale Co");

    expect(screen.getByRole("link", { name: "New supplier" })).toBeInTheDocument();
  });
});
