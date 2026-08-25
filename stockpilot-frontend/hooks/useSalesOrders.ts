"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listSalesOrders,
  getSalesOrder,
  createSalesOrder,
  updateSalesOrder,
  deleteSalesOrder,
  confirmSalesOrder,
  cancelSalesOrder,
  fulfillSalesOrder,
} from "../lib/api/salesOrders";
import type { ListParams } from "../lib/api/list-params";
import type { SalesOrder, SalesOrderFormValues } from "../lib/validation/salesOrders";

export function useSalesOrders(options: ListParams) {
  return useQuery({
    queryKey: ["sales-orders", options],
    queryFn: () => listSalesOrders(options),
  });
}

export function useSalesOrder(id: number) {
  return useQuery({
    queryKey: ["sales-orders", id],
    queryFn: () => getSalesOrder(id),
    enabled: !!id,
  });
}

export function useCreateSalesOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: SalesOrderFormValues) => createSalesOrder(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales-orders"] });
    },
  });
}

export function useUpdateSalesOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, values }: { id: number; values: SalesOrderFormValues }) =>
      updateSalesOrder(id, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales-orders"] });
    },
  });
}

export function useDeleteSalesOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteSalesOrder(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales-orders"] });
    },
  });
}

export function useConfirmSalesOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => confirmSalesOrder(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales-orders"] });
    },
  });
}

export function useCancelSalesOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => cancelSalesOrder(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales-orders"] });
    },
  });
}

export function useFulfillSalesOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => fulfillSalesOrder(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sales-orders"] });
    },
  });
}