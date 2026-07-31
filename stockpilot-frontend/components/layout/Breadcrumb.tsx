"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment } from "react";

function titleCase(segment: string): string {
  return segment
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function Breadcrumb() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  if (segments.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="px-4 py-2 text-[13px] text-[var(--color-text-mid)]">
      <ol className="flex items-center gap-1.5">
        {segments.map((segment, index) => {
          const href = `/${segments.slice(0, index + 1).join("/")}`;
          const isLast = index === segments.length - 1;
          return (
            <Fragment key={href}>
              {index > 0 && <span aria-hidden="true">/</span>}
              <li>
                {isLast ? (
                  <span className="text-[var(--color-text-hi)]">{titleCase(segment)}</span>
                ) : (
                  <Link href={href} className="hover:text-[var(--color-text-hi)]">
                    {titleCase(segment)}
                  </Link>
                )}
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
