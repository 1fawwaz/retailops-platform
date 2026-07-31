import * as Sentry from "@sentry/nextjs";

// docs/ARCHITECTURE.md § Monitoring and Logging: client-side error
// tracking, real-user performance monitoring on Dashboard/Inventory.
Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 0.1,
  sendDefaultPii: false,
});

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
