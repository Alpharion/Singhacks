"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { isFixtureMode } from "@/lib/api/config";
import { DemoPlaybackProvider } from "@/lib/demo/playback";

export function Providers({ children }: { children: ReactNode }) {
  // One client per browser session; created lazily so it is never shared
  // across requests during server rendering.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 1000, retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );

  const tree = <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;

  // The playback clock only exists in fixture mode. In live mode `usePlayback`
  // returns null and the controls hide themselves.
  return isFixtureMode ? <DemoPlaybackProvider>{tree}</DemoPlaybackProvider> : tree;
}
