import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SupplierDetailContent } from "./SupplierDetailContent";
import { setToken, clearToken } from "../../../../lib/auth/token";
import { setCachedPermissions, clearCachedPermissions } from "../../../../lib/auth/permissionsCache";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

const SUPPLIER = {
  _provenance: { lead_time_days: "derived", reliability_score: "derived" },
  _derivation_ref: {},
  id: 7,
  name: "Acme Wholesale Co",
  lead_time_days: 7,
  reliability_score: 0.92,
  created_at: "2026-01-01T00:00:00Z",
  skus: ["85048", "85049"],
};

const ROLLUP_ROW = {
  _provenance: {},
  _derivation_ref: {},
  supplier_id: 7,
  name: "Acme Wholesale Co",
  lead_time_days: 7,
  reliability_score: 0.92,
  sku_count: 2,
  total_inventory_value: 1200.5,
  open_purchase_order_count: 1,
  total_purchase_order_count: 3,
  on_time_delivery_rate: 0.85,
};

function mockRoutes(overrides: {
  supplier?: Response;
  rollup?: Response;
  contacts?: Response;
  purchaseOrders?: Response;
  deleteStatus?: number;
}) {
  const deleteStatus = overrides.deleteStatus ?? 204;
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      const path = new URL(url).pathname;
      if (init?.method === "DELETE" && path.startsWith("/suppliers/")) {
        return Promise.resolve(new Response(null, { status: deleteStatus }));
      }
      if (path === "/suppliers/7/contacts") return Promise.resolve(overrides.contacts);
      if (path === "/suppliers/7") return Promise.resolve(overrides.supplier);
      if (path === "/analytics/suppliers") return Promise.resolve(overrides.rollup);
      if (path === "/purchase-orders") return Promise.resolve(overrides.purchaseOrders);
      throw new Error(`Unexpected fetch to ${path}`);
    }),
  );
}

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SupplierDetailContent supplierId={7} />
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

describe("SupplierDetailContent", () => {
  it("renders lead time, reliability, and performance metrics", async () => {
    mockRoutes({
      supplier: jsonResponse(SUPPLIER),
      rollup: jsonResponse([ROLLUP_ROW]),
      contacts: jsonResponse([]),
      purchaseOrders: jsonResponse([]),
    });

    renderWithClient();

    expect(await screen.findByText("Acme Wholesale Co")).toBeInTheDocument();
    expect(screen.getByText("7d")).toBeInTheDocument();
    expect(await screen.findByText("85%")).toBeInTheDocument();
    expect(screen.getByText("₹1,201")).toBeInTheDocument();
  });

  it("shows a not-found empty state for a nonexistent supplier", async () => {
    mockRoutes({
      supplier: jsonResponse({ detail: "Not found" }, 404),
      rollup: jsonResponse([]),
      contacts: jsonResponse([]),
      purchaseOrders: jsonResponse([]),
    });

    renderWithClient();

    expect(await screen.findByText("Supplier not found")).toBeInTheDocument();
  });

  it("hides Edit/Delete when the user lacks the permissions", async () => {
    mockRoutes({
      supplier: jsonResponse(SUPPLIER),
      rollup: jsonResponse([ROLLUP_ROW]),
      contacts: jsonResponse([]),
      purchaseOrders: jsonResponse([]),
    });

    renderWithClient();
    await screen.findByText("Acme Wholesale Co");

    expect(screen.queryByRole("link", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("deletes the supplier and redirects to the list after confirming", async () => {
    const user = userEvent.setup();
    setCachedPermissions(["admin"], ["suppliers:update", "suppliers:delete"]);
    mockRoutes({
      supplier: jsonResponse(SUPPLIER),
      rollup: jsonResponse([ROLLUP_ROW]),
      contacts: jsonResponse([]),
      purchaseOrders: jsonResponse([]),
    });

    renderWithClient();
    await screen.findByText("Acme Wholesale Co");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/suppliers"));
  });

  it("shows a business-rule error and cancels the confirm state when delete is blocked", async () => {
    const user = userEvent.setup();
    setCachedPermissions(["admin"], ["suppliers:update", "suppliers:delete"]);
    mockRoutes({
      supplier: jsonResponse(SUPPLIER),
      rollup: jsonResponse([ROLLUP_ROW]),
      contacts: jsonResponse([]),
      purchaseOrders: jsonResponse([]),
      deleteStatus: 409,
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        const path = new URL(url).pathname;
        if (init?.method === "DELETE") {
          return Promise.resolve(
            jsonResponse({ detail: "Cannot delete a supplier with open purchase orders" }, 409),
          );
        }
        if (path === "/suppliers/7/contacts") return Promise.resolve(jsonResponse([]));
        if (path === "/suppliers/7") return Promise.resolve(jsonResponse(SUPPLIER));
        if (path === "/analytics/suppliers") return Promise.resolve(jsonResponse([ROLLUP_ROW]));
        if (path === "/purchase-orders") return Promise.resolve(jsonResponse([]));
        throw new Error(`Unexpected fetch to ${path}`);
      }),
    );

    renderWithClient();
    await screen.findByText("Acme Wholesale Co");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(
      await screen.findByText("Cannot delete a supplier with open purchase orders"),
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalledWith("/suppliers");
  });

  it("adds a contact and shows it in the list", async () => {
    const user = userEvent.setup();
    setCachedPermissions(["admin"], ["suppliers:update"]);
    const newContact = {
      id: 1,
      supplier_id: 7,
      name: "Priya Shah",
      email: null,
      phone: null,
      role: null,
      created_at: "2026-01-01T00:00:00Z",
    };
    let contactsCreated = false;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        const path = new URL(url).pathname;
        if (path === "/suppliers/7/contacts" && init?.method === "POST") {
          contactsCreated = true;
          return Promise.resolve(jsonResponse(newContact, 201));
        }
        if (path === "/suppliers/7/contacts") {
          return Promise.resolve(jsonResponse(contactsCreated ? [newContact] : []));
        }
        if (path === "/suppliers/7") return Promise.resolve(jsonResponse(SUPPLIER));
        if (path === "/analytics/suppliers") return Promise.resolve(jsonResponse([ROLLUP_ROW]));
        if (path === "/purchase-orders") return Promise.resolve(jsonResponse([]));
        throw new Error(`Unexpected fetch to ${path}`);
      }),
    );

    renderWithClient();
    await screen.findByText("Acme Wholesale Co");

    await user.click(screen.getByRole("button", { name: "Add contact" }));
    await user.type(screen.getByLabelText("Name"), "Priya Shah");
    await user.click(screen.getByRole("button", { name: "Save contact" }));

    expect(await screen.findByText("Priya Shah")).toBeInTheDocument();
  });
});
