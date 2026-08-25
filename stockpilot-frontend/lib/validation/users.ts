import { z } from "zod";

export const userWithRolesSchema = z.object({
  id: z.number().int(),
  email: z.string().email(),
  is_active: z.boolean(),
  is_read_only: z.boolean(),
  created_at: z.string(),
  roles: z.array(z.string()),
});
export type UserWithRoles = z.infer<typeof userWithRolesSchema>;

export const userListResponseSchema = z.array(userWithRolesSchema);

export const userCreateSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  full_name: z.string().optional(),
});
export type UserCreateValues = z.infer<typeof userCreateSchema>;