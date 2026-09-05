"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HandCoins, Store } from "lucide-react";
import { cn } from "@/lib/cn";

/**
 * Switch between the two sides of the marketplace.
 *
 * Both are the same product seen from opposite ends: a buyer delegates a budget
 * ceiling and an agent spends under it, a seller delegates a price floor and an
 * agent sells above it. Putting them behind one toggle is the clearest way to
 * say that.
 */
const SIDES = [
  { href: "/", label: "Buy", icon: HandCoins, match: (path: string) => !path.startsWith("/sell") },
  { href: "/sell", label: "Sell", icon: Store, match: (path: string) => path.startsWith("/sell") },
] as const;

export function SideToggle() {
  const pathname = usePathname() ?? "/";

  return (
    <nav
      aria-label="Marketplace side"
      className="flex items-center gap-0.5 rounded-full border border-border bg-surface p-0.5"
    >
      {SIDES.map(({ href, label, icon: Icon, match }) => {
        const active = match(pathname);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
              active
                ? "bg-rescue text-canvas"
                : "text-ink-muted hover:bg-surface-hover hover:text-ink",
            )}
          >
            <Icon className="size-3.5" aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
