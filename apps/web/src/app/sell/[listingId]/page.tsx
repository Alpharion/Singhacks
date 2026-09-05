import { ListingDashboard } from "@/components/seller/ListingDashboard";

/** `params` is a Promise in Next.js 16 and must be awaited before use. */
export default async function ListingPage({ params }: PageProps<"/sell/[listingId]">) {
  const { listingId } = await params;
  return <ListingDashboard listingId={listingId} />;
}
