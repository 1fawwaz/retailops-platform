// docs/ARCHITECTURE.md § Monitoring and Logging / BUILD.md Stage 0:
// "Error tracking wired... from day one." Registers Sentry for the
// server and edge runtimes. Sentry.init() with an empty/undefined dsn
// is a documented no-op (the SDK simply doesn't send anything) -- this
// file is safe to ship even before a real NEXT_PUBLIC_SENTRY_DSN is
// configured in Vercel, per .env.example's "placeholder, never a real
// value" convention.
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

export const onRequestError = async (
  ...args: Parameters<NonNullable<typeof import("@sentry/nextjs").captureRequestError>>
) => {
  const Sentry = await import("@sentry/nextjs");
  Sentry.captureRequestError(...args);
};
