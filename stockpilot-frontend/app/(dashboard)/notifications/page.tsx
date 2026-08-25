import { Suspense } from "react";
import { NotificationsContent } from "./NotificationsContent";

// docs/PRODUCT-SPEC.md §24 Notifications / §16 / BUILD.md Stage 9.
// Wired to real GET /notifications endpoint.
export default function NotificationsPage() {
  return (
    <Suspense fallback={null}>
      <NotificationsContent />
    </Suspense>
  );
}