import { Suspense } from "react";
import { UsersSettingsContent } from "./UsersSettingsContent";

// docs/PRODUCT-SPEC.md §24 User Management / BUILD.md Stage 9.
// Wired to real GET/POST /users, /users/{id}/roles endpoints.
export default function UsersSettingsPage() {
  return (
    <Suspense fallback={null}>
      <UsersSettingsContent />
    </Suspense>
  );
}