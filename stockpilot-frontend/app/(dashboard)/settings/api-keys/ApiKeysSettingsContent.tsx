"use client";

import { EmptyState } from "../../../../components/ui/EmptyState";

export function ApiKeysSettingsContent() {
  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">API Keys</h1>
      <p className="text-[13px] text-[var(--color-text-mid)]">
        API key management for machine-to-machine access will be available in a future release.
      </p>
      <EmptyState
        title="Not yet implemented"
        description="This feature is planned for a future release. For now, authentication uses JWT tokens via the standard login flow."
      />
    </div>
  );
}