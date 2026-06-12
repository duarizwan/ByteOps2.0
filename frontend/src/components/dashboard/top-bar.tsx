"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { UserButton } from "@clerk/nextjs";
import { Sun, Moon, Settings, HelpCircle } from "lucide-react";
import { useTheme } from "@/components/theme-provider";
import { ByteOpsLogoMark } from "@/lib/brand-icons";
import { useToolConnections } from "@/hooks/use-tool-connections";
import { TOOL_CAPABILITIES } from "@/lib/tool-capabilities";

export function TopBar() {
    const { resolvedTheme, setTheme, theme, mounted } = useTheme();
    const [showHelp, setShowHelp] = useState(false);
    const helpRef = useRef<HTMLDivElement>(null);
    const { connections } = useToolConnections();
    const connectedTools = connections.filter(c => c.status === "connected");

    const toggleTheme = () => {
        if (theme === "dark") setTheme("light");
        else if (theme === "light") setTheme("dark");
        else setTheme(resolvedTheme === "dark" ? "light" : "dark");
    };

    useEffect(() => {
        function handleClickOutside(e: MouseEvent) {
            if (helpRef.current && !helpRef.current.contains(e.target as Node)) {
                setShowHelp(false);
            }
        }
        if (showHelp) {
            document.addEventListener("mousedown", handleClickOutside);
        }
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [showHelp]);

    return (
        <div className="h-16 bg-card/95 backdrop-blur border-b border-border flex items-center justify-between px-6 sticky top-0 z-50">
            {/* Left — Branding */}
            <Link href="/dashboard" className="flex items-center gap-3 hover:opacity-80 hover:scale-[0.98] transition-all duration-150">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 bg-gradient-to-br from-blue-700 to-blue-500">
                    <ByteOpsLogoMark className="w-4 h-5" />
                </div>
                <div>
                    <h1 className="text-xl font-semibold text-foreground">ByteOps</h1>
                    <p className="text-xs text-muted-foreground">AI Work Assistant</p>
                </div>
            </Link>

            {/* Right — Actions */}
            <div className="flex items-center gap-3">
                {/* Theme Toggle */}
                <button
                    onClick={toggleTheme}
                    className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-accent transition-colors"
                    aria-label="Toggle theme"
                >
                    {mounted && resolvedTheme === "light" ? (
                        <Moon className="w-4 h-4 text-foreground" />
                    ) : (
                        <Sun className="w-4 h-4 text-foreground" />
                    )}
                </button>

                {/* Help */}
                <div className="relative" ref={helpRef}>
                    <button
                        onClick={() => setShowHelp(v => !v)}
                        className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-accent transition-colors"
                        aria-label="What can ByteOps do?"
                    >
                        <HelpCircle className="w-4 h-4 text-foreground" />
                    </button>

                    {showHelp && (
                        <div className="absolute right-0 top-10 z-50 w-72 rounded-xl border border-border bg-background shadow-lg p-4 text-sm">
                            <p className="font-medium text-foreground mb-3">What can I help you with?</p>
                            {connectedTools.length === 0 ? (
                                <p className="text-muted-foreground">
                                    Connect a tool in Settings → Connections to get started.
                                </p>
                            ) : (
                                <div className="space-y-3 max-h-64 overflow-y-auto custom-scrollbar">
                                    {connectedTools.map(tool => {
                                        const entry = TOOL_CAPABILITIES[tool.tool_type];
                                        if (!entry) return null;
                                        return (
                                            <div key={tool.tool_type}>
                                                <p className="font-medium text-foreground">{entry.label}</p>
                                                <ul className="mt-1 space-y-0.5">
                                                    {entry.capabilities.map(cap => (
                                                        <li key={cap} className="text-muted-foreground">
                                                            · {cap}
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Settings */}
                <Link
                    href="/settings"
                    className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-accent transition-colors"
                    title="Settings"
                >
                    <Settings className="w-4 h-4 text-foreground" />
                </Link>

                {/* User Avatar (Clerk) */}
                <UserButton
                    appearance={{
                        elements: {
                            avatarBox: "w-9 h-9 rounded-xl",
                        },
                    }}
                />
            </div>
        </div>
    );
}
