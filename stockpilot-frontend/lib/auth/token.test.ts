import { beforeEach, describe, expect, it } from "vitest";
import {
  clearToken,
  decodeToken,
  getRefreshToken,
  getToken,
  isTokenExpired,
  setAccessToken,
  setToken,
} from "./token";

// A real HS256 JWT shape (header.payload.signature), base64url-encoded --
// signature is a dummy string since this module never verifies it
// (docs/auth/token.ts's own docstring: decoding only, server always
// re-verifies per CLAUDE.md §12).
function makeToken(claims: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify(claims));
  return `${header}.${payload}.dummy-signature`;
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("token storage", () => {
  it("returns null when nothing is stored", () => {
    expect(getToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("round-trips both the access and refresh token", () => {
    setToken("abc.def.ghi", "refresh-123");
    expect(getToken()).toBe("abc.def.ghi");
    expect(getRefreshToken()).toBe("refresh-123");
  });

  it("clears both tokens", () => {
    setToken("abc.def.ghi", "refresh-123");
    clearToken();
    expect(getToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("setAccessToken updates only the access token, not the refresh token", () => {
    setToken("abc.def.ghi", "refresh-123");
    setAccessToken("new-access-token");
    expect(getToken()).toBe("new-access-token");
    expect(getRefreshToken()).toBe("refresh-123");
  });
});

describe("decodeToken", () => {
  it("decodes sub and exp from a well-formed token", () => {
    const token = makeToken({ sub: "user@example.com", exp: 9999999999 });
    expect(decodeToken(token)).toEqual({ sub: "user@example.com", exp: 9999999999 });
  });

  it("returns null for a malformed token (wrong number of segments)", () => {
    expect(decodeToken("not-a-jwt")).toBeNull();
  });

  it("returns null when the payload isn't valid JSON", () => {
    expect(decodeToken("aGVhZGVy.bm90LWpzb24.sig")).toBeNull();
  });

  it("returns null when required claims are missing", () => {
    const token = makeToken({ sub: "user@example.com" }); // no exp
    expect(decodeToken(token)).toBeNull();
  });
});

describe("isTokenExpired", () => {
  it("is false for a token expiring in the future", () => {
    const token = makeToken({ sub: "u", exp: Math.floor(Date.now() / 1000) + 3600 });
    expect(isTokenExpired(token)).toBe(false);
  });

  it("is true for a token that already expired", () => {
    const token = makeToken({ sub: "u", exp: Math.floor(Date.now() / 1000) - 3600 });
    expect(isTokenExpired(token)).toBe(true);
  });

  it("is true for an undecodable token", () => {
    expect(isTokenExpired("garbage")).toBe(true);
  });
});
