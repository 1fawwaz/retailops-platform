"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listCustomers,
  getCustomer,
  createCustomer,
  updateCustomer,
  deleteCustomer,
  getCustomerOrders,
} from "../lib/api/customers";
import type { ListParams } from "../lib/api/list-params";
import type { CustomerFormValues } from "../lib/validation/customers";

export function useCustomers(options: ListParams) {
  return useQuery({
    queryKey: ["customers", options],
    queryFn: () => listCustomers(options),
  });
}

export function useCustomer(id: number) {
  return useQuery({
    queryKey: ["customers", id],
    queryFn: () => getCustomer(id),
    enabled: !!id,
  });
}

export function useCreateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: CustomerFormValues) => createCustomer(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useUpdateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, values }: { id: number; values: CustomerFormValues }) =>
      updateCustomer(id, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useDeleteCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteCustomer(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useCustomerOrders(id: number) {
  return useQuery({
    queryKey: ["customers", id, "orders"],
    queryFn: () => getCustomerOrders(id),
    enabled: !!id,
  });
}