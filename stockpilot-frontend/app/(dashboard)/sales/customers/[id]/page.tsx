import { CustomerDetailContent } from "./CustomerDetailContent";

// docs/PRODUCT-SPEC.md §24 Customers detail.
export default async function CustomerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CustomerDetailContent id={Number(id)} />;
}