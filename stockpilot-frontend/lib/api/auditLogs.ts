import { apiFetch } from "./client";
import {
  auditLogListResponseSchema,
  type AuditLog,
  type AuditLogFilters,
} from "../validation/auditLogs";

export async function listAuditLogs(filters?: AuditLogFilters): Promise<AuditLog[]> {
  const raw = await apiFetch<unknown>("/audit-logs", {
    params: {
      user_id: filters?.user_id,
      permission: filters?.permission,
      outcome: filters?.outcome,
      date_from: filters?.date_from,
      date_to: filters?.date_to,
      limit: filters?.limit,
      offset: filters?.offset,
    },
  });
  return auditLogListResponseSchema.parse(raw);
}