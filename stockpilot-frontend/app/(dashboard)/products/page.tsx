import { EmptyState } from "../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Products / BUILD.md Stage 3.
export default function ProductsPage() {
  return (
    <EmptyState
      title="Products"
      description="Your product catalog will appear here once Stage 3 wires the products table and CRUD flows."
    />
  );
}
