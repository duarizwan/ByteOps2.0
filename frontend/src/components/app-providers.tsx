"use client";

import { ToolConnectionsProvider } from "@/providers/tool-connections-provider";

export function AppProviders({ children }: { children: React.ReactNode }) {
    return <ToolConnectionsProvider>{children}</ToolConnectionsProvider>;
}
