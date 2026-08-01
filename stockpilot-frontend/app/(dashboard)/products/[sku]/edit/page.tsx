import { EditProductContent } from "./EditProductContent";

// docs/PRODUCT-SPEC.md §24 Products "edit" action. Next.js 16: route
// params are async (a Promise), not a plain object -- must be awaited
// before use.
export default async function EditProductPage({
  params,
}: {
  params: Promise<{ sku: string }>;
}) {
  const { sku } = await params;
  return <EditProductContent sku={sku} />;
}
