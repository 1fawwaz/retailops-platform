import { InventoryDetailContent } from "./InventoryDetailContent";

// docs/PRODUCT-SPEC.md §24 Inventory Details / BUILD.md Stage 2.
// Next.js 16: route params are async (a Promise), not a plain object --
// must be awaited before use.
export default async function InventoryDetailPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return <InventoryDetailContent sku={sku} />;
}
