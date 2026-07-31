import { EmptyState } from "../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Inventory / BUILD.md Stage 2.
export default function InventoryPage() {
  return (
    <EmptyState
      title="Inventory"
      description="Stock levels across locations will appear here once Stage 2 wires the inventory table."
    />
  );
}
