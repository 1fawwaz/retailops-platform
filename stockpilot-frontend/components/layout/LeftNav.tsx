"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_GROUPS } from "./nav-config";
import { can } from "../../lib/rbac";

export function LeftNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary"
      className="w-56 shrink-0 border-r border-[var(--color-hairline)] bg-[var(--color-surface)] px-3 py-4"
    >
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="mb-6">
          <div className="mb-2 px-2 text-[11px] uppercase tracking-[0.04em] text-[var(--color-text-mid)]">
            {group.label}
          </div>
          <ul className="flex flex-col gap-0.5">
            {group.items.map((item) => {
              // RBAC gating is a UI convenience only (CLAUDE.md §12).
              // Uses the plain can() check, not the useCan() hook --
              // calling a hook inside .map() would violate the Rules of
              // Hooks; can() is the non-reactive equivalent
              // docs/ARCHITECTURE.md § Authorization calls for here.
              const visible = item.permission === undefined || can(item.permission);
              if (!visible) return null;
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`block rounded-[6px] px-2 py-1.5 text-[13px] transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)] ${
                      active
                        ? "bg-[var(--color-accent-dim)] text-[var(--color-text-hi)]"
                        : "text-[var(--color-text-mid)] hover:text-[var(--color-text-hi)]"
                    }`}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
