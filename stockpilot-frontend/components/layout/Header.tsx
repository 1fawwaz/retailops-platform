"use client";

import { useRouter } from "next/navigation";
import { useSession } from "../../lib/auth/useSession";
import { logout } from "../../lib/auth/session";

export function Header() {
  const router = useRouter();
  const session = useSession();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--color-hairline)] bg-[var(--color-surface)] px-4">
      <span className="font-mono text-[13px] text-[var(--color-text-mid)]" data-numeric>
        StockPilot
      </span>
      <div className="flex items-center gap-4">
        {session && (
          <span className="text-[13px] text-[var(--color-text-mid)]" data-testid="current-user-email">
            {session.email}
          </span>
        )}
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-[6px] px-2 py-1 text-[13px] text-[var(--color-text-mid)] transition-colors duration-150 hover:text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
        >
          Log out
        </button>
      </div>
    </header>
  );
}
