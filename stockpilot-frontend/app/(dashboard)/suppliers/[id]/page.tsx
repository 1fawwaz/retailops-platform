import { SupplierDetailContent } from "./SupplierDetailContent";

// docs/PRODUCT-SPEC.md §24 Suppliers detail. Next.js 16: route params
// are async (a Promise), not a plain object -- must be awaited before
// use.
export default async function SupplierDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <SupplierDetailContent supplierId={Number(id)} />;
}
