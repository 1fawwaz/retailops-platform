import { z } from "zod";

// Mirrors contracts/stockpilot-api/schemas/list_brands_route_brands_get.json exactly.
export const brandSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  created_at: z.string(),
});
export type Brand = z.infer<typeof brandSchema>;

export const brandListResponseSchema = z.array(brandSchema);

export const brandCreateSchema = z.object({
  name: z.string().min(1, "Name is required"),
});
export type BrandCreate = z.infer<typeof brandCreateSchema>;
