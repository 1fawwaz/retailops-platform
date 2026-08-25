import { Suspense } from "react";
import { RolesSettingsContent } from "./RolesSettingsContent";

// docs/PRODUCT-SPEC.md §24 Role Management / BUILD.md Stage 9.
// Wired to real GET/POST/PUT /roles, /roles/{id} endpoints.
export default function RolesSettingsPage() {
  return (
    <Suspense fallback={null}>
      <RolesSettingsContent />
    </Suspense>
  );
}