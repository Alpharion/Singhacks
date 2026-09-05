import type { NextConfig } from "next";

/**
 * Where the buyer agent is listening, as seen from the Next server (not the
 * browser). Server-side only, so it is deliberately not a `NEXT_PUBLIC_` name.
 */
const BUYER_AGENT_ORIGIN = process.env.BUYER_AGENT_ORIGIN ?? "http://localhost:8001";

const nextConfig: NextConfig = {
  /**
   * Proxy the contract's API surface to the buyer agent.
   *
   * The browser calls `/api/...` on this origin and Next forwards it to Person
   * 2's service. That keeps every request same-origin, which is what makes the
   * live mode work at all: the buyer agent is a plain FastAPI app with no CORS
   * middleware, so a direct cross-origin `fetch` from :3000 to :8001 fails its
   * preflight and never reaches the agent.
   *
   * Proxying rather than asking for CORS also keeps the browser off the
   * service's origin entirely, so the agent needs no opinion about which web
   * origins may call it.
   *
   * Point `NEXT_PUBLIC_BUYER_AGENT_BASE_URL` at an absolute URL to bypass this
   * and call the agent directly - that path does need CORS on the agent.
   */
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BUYER_AGENT_ORIGIN}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
