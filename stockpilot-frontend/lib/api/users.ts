import { apiFetch } from "./client";
import type { ListParams } from "./list-params";
import {
  userWithRolesSchema,
  userListResponseSchema,
  userCreateSchema,
  type UserWithRoles,
  type UserCreateValues,
} from "../validation/users";

export async function listUsers(options?: ListParams): Promise<UserWithRoles[]> {
  const raw = await apiFetch<unknown>("/users", {
    params: {
      limit: options?.limit,
      offset: options?.offset,
    },
  });
  return userListResponseSchema.parse(raw);
}

export async function createUser(values: UserCreateValues): Promise<UserWithRoles> {
  const raw = await apiFetch<unknown>("/users", {
    method: "POST",
    body: values,
  });
  return userWithRolesSchema.parse(raw);
}

export async function assignRole(userId: number, roleId: number): Promise<void> {
  await apiFetch<undefined>(`/users/${userId}/roles/${roleId}`, { method: "POST" });
}

export async function revokeRole(userId: number, roleId: number): Promise<void> {
  await apiFetch<undefined>(`/users/${userId}/roles/${roleId}`, { method: "DELETE" });
}