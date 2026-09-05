import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** The standard bordered surface every section of the dashboard sits on. */
export function Panel({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section
      className={cn("rounded-panel border border-border bg-surface", className)}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 border-b border-border px-5 py-3.5">
          <div className="min-w-0">
            {title && (
              <h2 className="text-[0.82rem] font-semibold uppercase tracking-[0.09em] text-ink-muted">
                {title}
              </h2>
            )}
            {subtitle && <p className="mt-1 text-sm text-ink-subtle">{subtitle}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className={cn("p-5", bodyClassName)}>{children}</div>
    </section>
  );
}

/** Shown in place of a panel's content before that step of the run has happened. */
export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="py-6 text-center text-sm text-ink-subtle">{children}</p>
  );
}
