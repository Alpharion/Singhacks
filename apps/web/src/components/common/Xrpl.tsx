import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/cn";

/**
 * A 64-hex XRPL transaction hash. Shown truncated with the full value in the
 * title attribute, and always selectable so it can be copied during a demo.
 */
export function TxHash({ hash, className }: { hash: string; className?: string }) {
  return (
    <code
      title={hash}
      className={cn(
        "select-all font-mono text-xs tracking-tight text-settled",
        className,
      )}
    >
      {hash.slice(0, 8)}…{hash.slice(-8)}
    </code>
  );
}

/** An XRPL classic address, truncated the same way. */
export function XrplAddr({ address, className }: { address: string; className?: string }) {
  return (
    <code
      title={address}
      className={cn("select-all font-mono text-xs text-ink-muted", className)}
    >
      {address.slice(0, 6)}…{address.slice(-4)}
    </code>
  );
}

/**
 * Link to the transaction on an explorer.
 *
 * `url` comes from `PaymentReceipt.explorerUrl` and is rendered exactly as the
 * backend supplied it. The frontend deliberately does not build explorer URLs -
 * choosing the network prefix is the payment layer's decision, not the UI's.
 */
export function ExplorerLink({
  url,
  hash,
  className,
}: {
  url: string;
  hash: string;
  className?: string;
}) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer noopener"
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 -mx-1.5 transition-colors hover:bg-settled-dim",
        className,
      )}
    >
      <TxHash hash={hash} />
      <ExternalLink className="size-3 shrink-0 text-ink-subtle" aria-hidden />
      <span className="sr-only">View transaction {hash} on the XRPL explorer</span>
    </a>
  );
}
