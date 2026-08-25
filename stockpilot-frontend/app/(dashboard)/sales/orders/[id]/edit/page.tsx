import { EditSalesOrderContent } from "../EditSalesOrderContent";

// docs/PRODUCT-SPEC.md §24 Sales "edit" action.
export default async function EditSalesOrderPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <EditSalesOrderContent id={Number(id)} />;
}