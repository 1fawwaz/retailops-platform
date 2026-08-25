import { SalesOrderDetailContent } from "./SalesOrderDetailContent";

// docs/PRODUCT-SPEC.md §24 Sales detail.
export default async function SalesOrderDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <SalesOrderDetailContent id={Number(id)} />;
}