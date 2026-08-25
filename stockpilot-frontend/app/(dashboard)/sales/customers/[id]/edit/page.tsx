import { EditCustomerContent } from "../EditCustomerContent";

// docs/PRODUCT-SPEC.md §24 Customers "edit" action.
export default async function EditCustomerPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <EditCustomerContent id={Number(id)} />;
}