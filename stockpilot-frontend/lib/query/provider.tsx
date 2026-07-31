"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

// docs/ARCHITECTURE.md § State Management: the client-side query cache
// for interactive lists and post-load mutations. One QueryClient per
// browser session (useState, not module scope) -- module scope would
// leak state across users in any future SSR-shared-process setup.
export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
          },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
