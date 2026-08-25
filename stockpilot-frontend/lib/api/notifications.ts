import { apiFetch } from "./client";
import type { ListParams } from "./list-params";
import {
  notificationSchema,
  notificationListResponseSchema,
  type Notification,
} from "../validation/notifications";

export async function listNotifications(options?: ListParams): Promise<Notification[]> {
  const raw = await apiFetch<unknown>("/notifications", {
    params: {
      limit: options?.limit,
      offset: options?.offset,
    },
  });
  return notificationListResponseSchema.parse(raw);
}

export async function markNotificationRead(id: number, isRead: boolean): Promise<Notification> {
  const raw = await apiFetch<unknown>(`/notifications/${id}`, {
    method: "PATCH",
    body: { is_read: isRead },
  });
  return notificationSchema.parse(raw);
}

export async function markAllNotificationsRead(): Promise<void> {
  await apiFetch<unknown>("/notifications/mark-all-read", { method: "POST" });
}