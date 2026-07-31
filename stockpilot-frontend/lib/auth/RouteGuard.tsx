"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "./useSession";

/**
 * docs/adr/001-session-management.md: the session lives in a
 * client-stored bearer token, not a cookie -- a Server Component
 * rendering app/(dashboard)/layout.tsx has no way to see it, so this
 * guard cannot run server-side the way a cookie-based session would
 * allow. useSession() (useSyncExternalStore) resolves the real client
 * snapshot as soon as it's available and self-corrects the SSR-vs-client
 * mismatch; the effect below only handles the actual redirect
 * (navigation, not local component state), preserving the original path
 * for post-login return (CLAUDE.md §12). Known, accepted consequence of
 * the ADR: a signed-out visitor landing directly on a protected URL sees
 * nothing rendered (session === null) until the redirect completes --
 * no business data fetch happens in that window, since nothing here
 * renders children without a session.
 */
export function RouteGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const session = useSession();

  useEffect(() => {
    if (session === null) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    }
  }, [session, router, pathname]);

  if (session === null) return null;
  return <>{children}</>;
}
