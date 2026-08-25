import { z } from "zod";

const provenanceMap = z.record(z.string(), z.string());

export const warehouseSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  created_at: z.string(),
  _provenance: provenanceMap.optional(),
  _derivation_ref: provenanceMap.optional(),
});
export type Warehouse = z.infer<typeof warehouseSchema>;
export const warehouseListResponseSchema = z.array(warehouseSchema);