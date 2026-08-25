import { PurchaseOrderDetailContent } from "./PurchaseOrderDetailContent";

export default async function PurchaseOrderDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PurchaseOrderDetailContent poId={Number(id)} />;
}