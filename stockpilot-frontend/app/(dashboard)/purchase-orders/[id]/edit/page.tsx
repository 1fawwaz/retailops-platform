import { EditPurchaseOrderContent } from "./EditPurchaseOrderContent";

export default async function EditPurchaseOrderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <EditPurchaseOrderContent poId={Number(id)} />;
}