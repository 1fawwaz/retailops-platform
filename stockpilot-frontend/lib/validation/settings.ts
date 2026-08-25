import { z } from "zod";

export const settingsSchema = z.object({
  currency: z.string(),
  timezone: z.string(),
  low_stock_notifications_enabled: z.boolean(),
  updated_at: z.string(),
});
export type Settings = z.infer<typeof settingsSchema>;

export const settingsFormSchema = z.object({
  currency: z.string().min(1, "Currency is required"),
  timezone: z.string().min(1, "Timezone is required"),
  low_stock_notifications_enabled: z.boolean(),
});
export type SettingsFormValues = z.infer<typeof settingsFormSchema>;