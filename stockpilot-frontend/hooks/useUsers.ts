"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listUsers, createUser, assignRole, revokeRole } from "../lib/api/users";
import type { ListParams } from "../lib/api/list-params";
import type { UserWithRoles, UserCreateValues } from "../lib/validation/users";

export function useUsers(options?: ListParams) {
  return useQuery({
    queryKey: ["users", options],
    queryFn: () => listUsers(options),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: UserCreateValues) => createUser(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useAssignRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleId }: { userId: number; roleId: number }) =>
      assignRole(userId, roleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useRevokeRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleId }: { userId: number; roleId: number }) =>
      revokeRole(userId, roleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}