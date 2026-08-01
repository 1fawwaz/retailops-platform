import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginForm } from "./LoginForm";
import { clearToken } from "../../../lib/auth/token";

// BUILD.md Stage 0's own required test: "Integration: login flow
// (success, failure, expired-token redirect)." The expired-token
// redirect half is covered by lib/auth/RouteGuard's own behavior
// (session === null -> redirect); this file covers login itself.

const replace = vi.fn();
let searchParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => searchParams,
}));

function makeToken(claims: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify(claims));
  return `${header}.${payload}.dummy-signature`;
}

beforeEach(() => {
  window.localStorage.clear();
  replace.mockClear();
  searchParams = new URLSearchParams();
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearToken();
});

describe("LoginForm", () => {
  it("stores the token and redirects to /dashboard on valid credentials", async () => {
    const user = userEvent.setup();
    const token = makeToken({ sub: "priya@example.com", exp: 9999999999 });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ access_token: token, refresh_token: "test-refresh-token", token_type: "bearer" }), {
          status: 200,
        }),
      ),
    );

    render(<LoginForm />);
    await user.type(screen.getByLabelText("Email"), "priya@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(window.localStorage.getItem("stockpilot.access_token")).toBe(token);
  });

  it("shows a specific error and does not redirect on invalid credentials", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Incorrect username or password" }), {
          status: 401,
        }),
      ),
    );

    render(<LoginForm />);
    await user.type(screen.getByLabelText("Email"), "priya@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
    expect(replace).not.toHaveBeenCalled();
    expect(window.localStorage.getItem("stockpilot.access_token")).toBeNull();
  });

  it("returns to the original destination (?redirect=) after a session-expiry redirect to login", async () => {
    // The scenario BUILD.md Stage 0 actually asks for: RouteGuard sends
    // an expired/missing session to /login?redirect=/inventory; login
    // must return the user there, not always to /dashboard.
    searchParams = new URLSearchParams({ redirect: "/inventory" });
    const user = userEvent.setup();
    const token = makeToken({ sub: "priya@example.com", exp: 9999999999 });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ access_token: token, refresh_token: "test-refresh-token", token_type: "bearer" }), {
          status: 200,
        }),
      ),
    );

    render(<LoginForm />);
    await user.type(screen.getByLabelText("Email"), "priya@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/inventory"));
  });

  it("ignores a redirect param that isn't a same-origin path (open-redirect guard)", async () => {
    searchParams = new URLSearchParams({ redirect: "https://evil.example/phish" });
    const user = userEvent.setup();
    const token = makeToken({ sub: "priya@example.com", exp: 9999999999 });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ access_token: token, refresh_token: "test-refresh-token", token_type: "bearer" }), {
          status: 200,
        }),
      ),
    );

    render(<LoginForm />);
    await user.type(screen.getByLabelText("Email"), "priya@example.com");
    await user.type(screen.getByLabelText("Password"), "correct-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });
});
