"use client";

// docs/ARCHITECTURE.md § Error Handling Architecture: route-level
// error.tsx per segment, never a raw stack trace to the user. This is
// the top-of-segment catch-all; a resource page can add its own more
// specific error.tsx later without removing this one (Next.js uses the
// nearest boundary).
export default function DashboardSegmentError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-center">
      <h2 className="text-[16px] font-medium text-[var(--color-text-hi)]">
        Something went wrong loading this page.
      </h2>
      <p className="max-w-[40ch] text-[13px] text-[var(--color-text-mid)]">
        {error.digest ? `Reference: ${error.digest}` : "Please try again."}
      </p>
      <button
        type="button"
        onClick={reset}
        className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
      >
        Retry
      </button>
    </div>
  );
}
