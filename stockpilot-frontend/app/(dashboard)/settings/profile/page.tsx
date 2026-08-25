import { Suspense } from "react";
import { ProfileSettingsContent } from "./ProfileSettingsContent";

// docs/PRODUCT-SPEC.md §24 Profile / FR-14 / BUILD.md Stage 9.
export default function ProfileSettingsPage() {
  return (
    <Suspense fallback={null}>
      <ProfileSettingsContent />
    </Suspense>
  );
}