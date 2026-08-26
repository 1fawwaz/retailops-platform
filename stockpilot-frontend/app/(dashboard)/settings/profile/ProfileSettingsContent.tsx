"use client";

import { useSettings } from "../../../../hooks/useSettings";
import { AppError } from "../../../../lib/api/errors";

export function ProfileSettingsContent() {
  const settings = useSettings();

  if (settings.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      </div>
    );
  }

  if (settings.isError) {
    return (
      <p className="pt-4 text-[13px] text-[var(--color-danger)]">
        {settings.error instanceof AppError ? settings.error.message : "Could not load settings."}
      </p>
    );
  }

  const data = settings.data;

  return (
    <div className="flex flex-col gap-6 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">Profile</h1>

      <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
        <h2 className="mb-4 text-[16px] font-medium text-[var(--color-text-hi)]">System Settings</h2>
        {data && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-[13px] text-[var(--color-text-mid)]">Currency</div>
              <div className="font-mono text-[14px] text-[var(--color-text-hi)]">{data.currency}</div>
            </div>
            <div>
              <div className="text-[13px] text-[var(--color-text-mid)]">Timezone</div>
              <div className="font-mono text-[14px] text-[var(--color-text-hi)]">{data.timezone}</div>
            </div>
            <div>
              <div className="text-[13px] text-[var(--color-text-mid)]">Low Stock Notifications</div>
              <div className="font-mono text-[14px] text-[var(--color-text-hi)]">
                {data.low_stock_notifications_enabled ? "Enabled" : "Disabled"}
              </div>
            </div>
            <div>
              <div className="text-[13px] text-[var(--color-text-mid)]">Last Updated</div>
              <div className="font-mono text-[14px] text-[var(--color-text-hi)]" data-numeric>
                {new Date(data.updated_at).toLocaleString("en-GB")}
              </div>
            </div>
          </div>
        )}
      </div>

      <p className="text-[13px] text-[var(--color-text-mid)]">
        Profile management (password change, notification preferences, etc.) will be available in a future release.
      </p>
    </div>
  );
}