// docs/ARCHITECTURE.md § Error Handling Architecture: every StockPilot
// Core error response is normalized to exactly one of these kinds before
// a component ever sees it -- no raw fetch/HTTP error reaches UI code.
export type AppErrorKind =
  | "network"
  | "auth"
  | "validation"
  | "business-rule"
  | "server"
  | "unknown";

export interface AppErrorFieldIssue {
  field: string;
  message: string;
}

export class AppError extends Error {
  readonly kind: AppErrorKind;
  readonly fields?: AppErrorFieldIssue[];
  readonly status?: number;

  constructor(
    kind: AppErrorKind,
    message: string,
    options?: { fields?: AppErrorFieldIssue[]; status?: number; cause?: unknown },
  ) {
    super(message, { cause: options?.cause });
    this.name = "AppError";
    this.kind = kind;
    this.fields = options?.fields;
    this.status = options?.status;
  }
}

// FastAPI's 422 shape: { detail: [{ loc: ["body", "field"], msg, type }] }
interface FastApiValidationError {
  detail: Array<{ loc: (string | number)[]; msg: string; type: string }>;
}

function isFastApiValidationError(value: unknown): value is FastApiValidationError {
  return (
    typeof value === "object" &&
    value !== null &&
    Array.isArray((value as { detail?: unknown }).detail)
  );
}

/**
 * Normalizes a StockPilot Core HTTP response into an AppError. Called by
 * lib/api/client.ts on any non-2xx response -- the only place raw
 * response.status/response.json() is read directly.
 */
export async function toAppError(response: Response): Promise<AppError> {
  if (response.status === 401) {
    return new AppError("auth", "Your session has expired. Please log in again.", {
      status: response.status,
    });
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (response.status === 422 && isFastApiValidationError(body)) {
    return new AppError("validation", "Some fields need attention.", {
      status: response.status,
      fields: body.detail.map((issue) => ({
        field: issue.loc[issue.loc.length - 1]?.toString() ?? "unknown",
        message: issue.msg,
      })),
    });
  }

  if (response.status >= 400 && response.status < 500) {
    const detail =
      body && typeof body === "object" && "detail" in body && typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status}).`;
    return new AppError("business-rule", detail, { status: response.status });
  }

  if (response.status >= 500) {
    return new AppError(
      "server",
      "Something went wrong on our end. Please try again in a moment.",
      { status: response.status },
    );
  }

  return new AppError("unknown", "An unexpected error occurred.", { status: response.status });
}

export function networkAppError(cause: unknown): AppError {
  return new AppError("network", "Could not reach the server. Check your connection.", {
    cause,
  });
}
