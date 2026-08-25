"use client";

import { useQuery } from "@tanstack/react-query";
import { listAuditLogs } from "../lib/api/auditLogs";
import type { AuditLogFilters } from "../lib/validation/auditLogs";

export function useAuditLogs(filters?: AuditLogFilters) {
  return useQuery({
    queryKey: ["audit-logs", filters],
    queryFn: () => listAuditLogs(filters),
  });
}