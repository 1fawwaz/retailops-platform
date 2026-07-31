import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 0.1,
  // No PII beyond what's already in session claims -- docs/ARCHITECTURE.md
  // § Monitoring and Logging.
  sendDefaultPii: false,
});
