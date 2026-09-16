/**
 * Centralized resolution and client helpers for RetailOps AI service.
 * Supports NEXT_PUBLIC_AI_API_URL and NEXT_PUBLIC_AI_BASE_URL with local fallback.
 */

export function getAiBaseUrl(): string {
  const envUrl =
    process.env.NEXT_PUBLIC_AI_API_URL ||
    process.env.NEXT_PUBLIC_AI_BASE_URL;

  if (envUrl && envUrl.trim()) {
    // If running in browser on remote host but envUrl points to localhost, fall back to production AI URL
    if (
      typeof window !== "undefined" &&
      window.location.hostname !== "localhost" &&
      window.location.hostname !== "127.0.0.1" &&
      envUrl.includes("localhost")
    ) {
      return "https://retailops-ai.onrender.com";
    }
    return envUrl.replace(/\/+$/, "");
  }

  // Browser remote fallback
  if (
    typeof window !== "undefined" &&
    window.location.hostname !== "localhost" &&
    window.location.hostname !== "127.0.0.1"
  ) {
    return "https://retailops-ai.onrender.com";
  }

  return process.env.NODE_ENV === "production"
    ? "https://retailops-ai.onrender.com"
    : "http://localhost:8001";
}

export function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (envUrl && envUrl.trim()) {
    if (
      typeof window !== "undefined" &&
      window.location.hostname !== "localhost" &&
      window.location.hostname !== "127.0.0.1" &&
      envUrl.includes("localhost")
    ) {
      return "https://retail-hta8.onrender.com";
    }
    return envUrl.replace(/\/+$/, "");
  }

  if (
    typeof window !== "undefined" &&
    window.location.hostname !== "localhost" &&
    window.location.hostname !== "127.0.0.1"
  ) {
    return "https://retail-hta8.onrender.com";
  }

  return process.env.NODE_ENV === "production"
    ? "https://retail-hta8.onrender.com"
    : "http://localhost:8000";
}

if (typeof window !== "undefined" && process.env.NODE_ENV === "development") {
  console.log(`[StockPilot Frontend] Resolved Core API: ${getApiBaseUrl()}, AI Service: ${getAiBaseUrl()}`);
}
