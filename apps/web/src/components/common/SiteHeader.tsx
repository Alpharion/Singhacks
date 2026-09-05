import Link from "next/link";
import { Sprout } from "lucide-react";
import { FixtureBadge } from "./FixtureBadge";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-canvas/85 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-6 py-3">
        <Link href="/" className="flex items-center gap-2.5 group">
          <span className="grid size-8 place-items-center rounded-lg bg-rescue-dim ring-1 ring-inset ring-rescue/25">
            <Sprout className="size-4 text-rescue" aria-hidden />
          </span>
          <span className="flex flex-col leading-none">
            <span className="text-sm font-semibold tracking-tight text-ink group-hover:text-rescue transition-colors">
              SurplusFlow
            </span>
            <span className="mt-0.5 text-[0.68rem] text-ink-subtle">
              Agentic procurement on XRPL
            </span>
          </span>
        </Link>

        <div className="ml-auto flex items-center gap-3">
          <FixtureBadge />
        </div>
      </div>
    </header>
  );
}
