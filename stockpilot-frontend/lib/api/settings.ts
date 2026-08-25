import { apiFetch } from "./client";
import {
  settingsSchema,
  settingsFormSchema,
  type Settings,
  type SettingsFormValues,
} from "../validation/settings";

export async function getSettings(): Promise<Settings> {
  const raw = await apiFetch<unknown>("/settings");
  return settingsSchema.parse(raw);
}

export async function updateSettings(values: SettingsFormValues): Promise<Settings> {
  const raw = await apiFetch<unknown>("/settings", {
    method: "PUT",
    body: values,
  });
  return settingsSchema.parse(raw);
}