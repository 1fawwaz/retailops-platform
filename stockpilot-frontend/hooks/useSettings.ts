"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSettings, updateSettings } from "../lib/api/settings";
import type { Settings, SettingsFormValues } from "../lib/validation/settings";

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: () => getSettings(),
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: SettingsFormValues) => updateSettings(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });
}