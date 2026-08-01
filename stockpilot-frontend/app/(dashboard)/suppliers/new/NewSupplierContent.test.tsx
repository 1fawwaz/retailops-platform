import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NewSupplierContent } from "./NewSupplierContent";
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
      <NewSupplierContent />
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

describe("NewSupplierContent", () => {
  it("shows a permission-denied empty state when the user lacks suppliers:create", () => {
    renderWithClient();

    expect(
      screen.getByText("You don't have permission to create suppliers"),
    ).toBeInTheDocument();
  });

  it("submits the form and redirects to the new supplier's detail page", async () => {
    const user = userEvent.setup();
    setCachedPermissions(["admin"], ["suppliers:create"]);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        const path = new URL(url).pathname;
        if (path === "/suppliers" && init?.method === "POST") {
          return Promise.resolve(
            jsonResponse(
              {
                _provenance: {},
                _derivation_ref: {},
                id: 22,
                name: "New Co",
                lead_time_days: 5,
                reliability_score: 0.9,
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
    await user.type(screen.getByLabelText("Name"), "New Co");
    await user.clear(screen.getByLabelText("Lead time (days)"));
    await user.type(screen.getByLabelText("Lead time (days)"), "5");
    await user.clear(screen.getByLabelText("Reliability score (0-1)"));
    await user.type(screen.getByLabelText("Reliability score (0-1)"), "0.9");
    await user.click(screen.getByRole("button", { name: "Create supplier" }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/suppliers/22"));
  });

  it("shows a validation error when reliability score is out of range", async () => {
    const user = userEvent.setup();
    setCachedPermissions(["admin"], ["suppliers:create"]);
    vi.stubGlobal("fetch", vi.fn());

    renderWithClient();
    await user.type(screen.getByLabelText("Name"), "New Co");
    await user.clear(screen.getByLabelText("Reliability score (0-1)"));
    await user.type(screen.getByLabelText("Reliability score (0-1)"), "1.5");
    await user.click(screen.getByRole("button", { name: "Create supplier" }));

    expect(await screen.findByText("Must be between 0 and 1")).toBeInTheDocument();
  });
});
