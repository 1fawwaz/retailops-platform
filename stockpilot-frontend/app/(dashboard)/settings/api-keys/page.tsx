import { Suspense } from "react";
import { ApiKeysSettingsContent } from "./ApiKeysSettingsContent";

// docs/PRODUCT-SPEC.md §24 Settings / BUILD.md Stage 9.
export default function ApiKeysSettingsPage() {
  return (
    <Suspense fallback={null}>
      <ApiKeysSettingsContent />
    </Suspense>
  );
}