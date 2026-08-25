"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listRoles, getRole, createRole, updateRole } from "../lib/api/roles";
import type { ListParams } from "../lib/api/list-params";
import type { Role, RoleFormValues } from "../lib/validation/roles";

export function useRoles(options?: ListParams) {
  return useQuery({
    queryKey: ["roles", options],
    queryFn: () => listRoles(options),
  });
}

export function useRole(id: number) {
  return useQuery({
    queryKey: ["roles", id],
    queryFn: () => getRole(id),
    enabled: !!id,
  });
}

export function useCreateRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: RoleFormValues) => createRole(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
    },
  });
}

export function useUpdateRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, values }: { id: number; values: RoleFormValues }) =>
      updateRole(id, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["roles"] });
    },
  });
}