import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  /* config options here */
};

// withSentryConfig is safe with no SENTRY_AUTH_TOKEN set (dev, or before
// a real Sentry project exists) -- it silently skips source map upload
// rather than failing the build, per Sentry's own documented behavior.
export default withSentryConfig(nextConfig, {
  silent: true,
  widenClientFileUpload: true,
});
