"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listNotifications, markNotificationRead, markAllNotificationsRead } from "../lib/api/notifications";
import type { ListParams } from "../lib/api/list-params";
import type { Notification } from "../lib/validation/notifications";

export function useNotifications(options?: ListParams) {
  return useQuery({
    queryKey: ["notifications", options],
    queryFn: () => listNotifications(options),
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isRead }: { id: number; isRead: boolean }) =>
      markNotificationRead(id, isRead),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => markAllNotificationsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}