import { EmptyState } from "../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Suppliers / BUILD.md Stage 4.
export default function SuppliersPage() {
  return (
    <EmptyState
      title="Suppliers"
      description="Your supplier list will appear here once Stage 4 wires supplier records and purchase history."
    />
  );
}
