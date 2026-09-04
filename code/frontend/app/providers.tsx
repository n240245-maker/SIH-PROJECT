"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ScopeProvider } from "@/lib/scope";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: {
    staleTime: 60_000, retry: 1, refetchOnWindowFocus: false,
  } } }));
  return <QueryClientProvider client={client}><ScopeProvider>{children}</ScopeProvider></QueryClientProvider>;
}
