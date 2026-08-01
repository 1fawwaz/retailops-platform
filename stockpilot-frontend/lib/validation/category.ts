import { z } from "zod";

// Mirrors contracts/stockpilot-api/schemas/list_categories_route_categories_get.json exactly.
export const categorySchema = z.object({
  id: z.number().int(),
  name: z.string(),
  created_at: z.string(),
});
export type Category = z.infer<typeof categorySchema>;

export const categoryListResponseSchema = z.array(categorySchema);

export const categoryCreateSchema = z.object({
  name: z.string().min(1, "Name is required"),
});
export type CategoryCreate = z.infer<typeof categoryCreateSchema>;
