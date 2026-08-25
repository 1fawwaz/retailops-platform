import { Suspense } from "react";
import { AuditLogsContent } from "./AuditLogsContent";

// docs/PRODUCT-SPEC.md §24 Audit Logs / BUILD.md Stage 9.
// Wired to real GET /audit-logs endpoint.
export default function AuditLogsPage() {
  return (
    <Suspense fallback={null}>
      <AuditLogsContent />
    </Suspense>
  );
}