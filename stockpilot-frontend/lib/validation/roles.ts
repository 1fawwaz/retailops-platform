import { z } from "zod";

export const roleSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  permissions: z.array(z.string()),
  created_at: z.string(),
});
export type Role = z.infer<typeof roleSchema>;

export const roleListResponseSchema = z.array(roleSchema);

export const roleFormSchema = z.object({
  name: z.string().min(1, "Role name is required"),
  permissions: z.array(z.string()),
});
export type RoleFormValues = z.infer<typeof roleFormSchema>;