/**
 * Centralized resolution and client helpers for RetailOps AI service.
 * Supports NEXT_PUBLIC_AI_API_URL and NEXT_PUBLIC_AI_BASE_URL with local fallback.
 */

export function getAiBaseUrl(): string {
  const url =
    process.env.NEXT_PUBLIC_AI_API_URL ||
    process.env.NEXT_PUBLIC_AI_BASE_URL ||
    "http://localhost:8001";
  return url.replace(/\/+$/, "");
}

export function getApiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  return url.replace(/\/+$/, "");
}

if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
  console.log(`[StockPilot Frontend] Resolved Core API: ${getApiBaseUrl()}, AI Service: ${getAiBaseUrl()}`);
}
