import { apiFetch } from "./client";
import type { ListParams } from "./list-params";
import {
  roleSchema,
  roleListResponseSchema,
  roleFormSchema,
  type Role,
  type RoleFormValues,
} from "../validation/roles";

export async function listRoles(options?: ListParams): Promise<Role[]> {
  const raw = await apiFetch<unknown>("/roles", {
    params: {
      limit: options?.limit,
      offset: options?.offset,
    },
  });
  return roleListResponseSchema.parse(raw);
}

export async function getRole(id: number): Promise<Role> {
  const raw = await apiFetch<unknown>(`/roles/${id}`);
  return roleSchema.parse(raw);
}

export async function createRole(values: RoleFormValues): Promise<Role> {
  const raw = await apiFetch<unknown>("/roles", {
    method: "POST",
    body: values,
  });
  return roleSchema.parse(raw);
}

export async function updateRole(id: number, values: RoleFormValues): Promise<Role> {
  const raw = await apiFetch<unknown>(`/roles/${id}`, {
    method: "PUT",
    body: values,
  });
  return roleSchema.parse(raw);
}