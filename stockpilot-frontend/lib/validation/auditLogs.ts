import { z } from "zod";

export const auditLogSchema = z.object({
  id: z.number().int(),
  user_id: z.number().int(),
  permission: z.string(),
  method: z.string(),
  path: z.string(),
  outcome: z.string(),
  created_at: z.string(),
});
export type AuditLog = z.infer<typeof auditLogSchema>;

export const auditLogListResponseSchema = z.array(auditLogSchema);

export const auditLogFiltersSchema = z.object({
  user_id: z.number().int().optional(),
  permission: z.string().optional(),
  outcome: z.string().optional(),
  date_from: z.string().optional(),
  date_to: z.string().optional(),
  limit: z.number().int().optional(),
  offset: z.number().int().optional(),
});
export type AuditLogFilters = z.infer<typeof auditLogFiltersSchema>;