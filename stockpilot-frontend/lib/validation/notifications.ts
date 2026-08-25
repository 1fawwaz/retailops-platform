import { z } from "zod";

export const notificationSchema = z.object({
  id: z.number().int(),
  type: z.string(),
  message: z.string(),
  resource_type: z.string().nullable(),
  resource_id: z.string().nullable(),
  is_read: z.boolean(),
  created_at: z.string(),
});
export type Notification = z.infer<typeof notificationSchema>;

export const notificationListResponseSchema = z.array(notificationSchema);

export const markNotificationReadSchema = z.object({
  is_read: z.boolean(),
});