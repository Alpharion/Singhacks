"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import { useCreateListing } from "@/lib/seller/queries";
import { demoListingText } from "@/lib/seller/demoListing";
import { cn } from "@/lib/cn";

const SELLER_ID = "seller_bakery_001";

/**
 * The only thing the seller does: say what is going spare, and the one price
 * they will not go under.
 *
 * Everything after that - the opening ask, every reduction, when to hold - is
 * the agent's call inside that floor.
 */
export function ListingForm() {
  const router = useRouter();
  const createListing = useCreateListing();
  const [requestText, setRequestText] = useState(demoListingText(new Date(0)));
  const [edited, setEdited] = useState(false);

  useEffect(() => {
    if (edited) return;
    // Same reason as the buyer form: the collection deadline is a wall-clock
    // time, and only the client can read the clock without hydrating mismatched.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRequestText(demoListingText());
  }, [edited]);

  const isSubmitting = createListing.isPending;
  const tooShort = requestText.trim().length < 10;

  async function handleSubmit(formEvent: React.FormEvent) {
    formEvent.preventDefault();
    if (tooShort || isSubmitting) return;

    const listing = await createListing.mutateAsync({
      sellerId: SELLER_ID,
      requestText: requestText.trim(),
    });
    router.push(`/sell/${listing.listingId}`);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label
          htmlFor="listingText"
          className="block text-[0.7rem] font-medium uppercase tracking-[0.09em] text-ink-subtle"
        >
          What are you selling?
        </label>
        <textarea
          id="listingText"
          name="listingText"
          rows={4}
          value={requestText}
          onChange={(changeEvent) => {
            setEdited(true);
            setRequestText(changeEvent.target.value);
          }}
          maxLength={1000}
          className={cn(
            "mt-2 w-full resize-none rounded-xl border border-border bg-canvas px-4 py-3.5",
            "text-[0.95rem] leading-relaxed text-ink placeholder:text-ink-subtle",
            "outline-none transition-colors focus:border-rescue/50 focus:ring-2 focus:ring-rescue/15",
          )}
          placeholder="Sell 60 vegetarian bakery meal boxes, collection by 9 PM, asking 2 XRP each but no less than 1.20 XRP."
        />
        <p className="mt-1.5 text-xs text-ink-subtle">
          State a quantity, a collection deadline, and the lowest unit price you will
          accept. The agent will not list without a floor — it refuses to guess what your
          food is worth.
        </p>
      </div>

      {createListing.error && (
        <p className="rounded-lg bg-rejected-dim px-3.5 py-2.5 text-sm text-rejected">
          {createListing.error.message}
        </p>
      )}

      <button
        type="submit"
        disabled={tooShort || isSubmitting}
        className={cn(
          "inline-flex w-full items-center justify-center gap-2 rounded-xl px-5 py-3",
          "text-sm font-semibold transition-all",
          "bg-rescue text-canvas hover:brightness-110",
          "disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:brightness-100",
        )}
      >
        {isSubmitting ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Listing…
          </>
        ) : (
          <>
            Hand pricing to the agent
            <ArrowRight className="size-4" aria-hidden />
          </>
        )}
      </button>
    </form>
  );
}
