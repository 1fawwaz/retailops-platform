"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

// Sentry's own recommended pattern: global-error.tsx is the root-level
// catch-all for errors that escape every segment's own error.tsx
// (app/(dashboard)/error.tsx) -- it must render its own <html>/<body>
// since it replaces the root layout entirely when it fires.
export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string };
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <div style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center" }}>
          <p>Something went wrong. Please refresh the page.</p>
        </div>
      </body>
    </html>
  );
}
