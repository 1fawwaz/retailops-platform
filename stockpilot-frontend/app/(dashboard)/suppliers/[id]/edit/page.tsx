import { EditSupplierContent } from "./EditSupplierContent";

// docs/PRODUCT-SPEC.md §24 Suppliers "edit" action. Next.js 16: route
// params are async (a Promise), not a plain object -- must be awaited
// before use.
export default async function EditSupplierPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <EditSupplierContent supplierId={Number(id)} />;
}
