import { ProductDetailContent } from "./ProductDetailContent";

// docs/PRODUCT-SPEC.md §24 Products detail. Next.js 16: route params are
// async (a Promise), not a plain object -- must be awaited before use.
export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return <ProductDetailContent sku={sku} />;
}
