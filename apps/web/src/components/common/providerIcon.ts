import { Croissant, Drumstick, Soup, Store, Truck, type LucideIcon } from "lucide-react";

/**
 * A food icon for each provider, so a bakery looks like a bakery.
 *
 * Presentation only. The contract carries `sellerName` and ids but no category, so this
 * is the frontend's own reading of the demo providers - it changes an icon and a caption
 * and nothing else. No price, quantity, availability or decision is derived from it.
 *
 * Provider behaviour - pricing, expiry, stock and sold-out handling - belongs to
 * Person 3's services (PROJECT_CONTEXT.md section 11) and is never inferred here.
 *
 * Unknown ids fall back to a generic shop or van rather than breaking, because the live
 * marketplace may return providers this map has never seen.
 */

export interface ProviderIcon {
  icon: LucideIcon;
  /** Short human label, e.g. "Bakery". */
  kind: string;
}

const ICONS: Record<string, ProviderIcon> = {
  seller_bakery_001: { icon: Croissant, kind: "Bakery" },
  seller_hotel_001: { icon: Soup, kind: "Hotel kitchen" },
  seller_grill_001: { icon: Drumstick, kind: "Grill" },
  courier_fast_001: { icon: Truck, kind: "Courier" },
  courier_economy_001: { icon: Truck, kind: "Courier" },
};

const UNKNOWN_SELLER: ProviderIcon = { icon: Store, kind: "Food business" };
const UNKNOWN_COURIER: ProviderIcon = { icon: Truck, kind: "Courier" };

export function providerIcon(id: string): ProviderIcon {
  return ICONS[id] ?? (id.startsWith("courier") ? UNKNOWN_COURIER : UNKNOWN_SELLER);
}
