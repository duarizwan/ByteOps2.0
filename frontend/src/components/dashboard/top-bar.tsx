"use client";

import Link from "next/link";
import { UserButton } from "@clerk/nextjs";
import { Sun, Moon, Settings } from "lucide-react";
import { useTheme } from "@/components/theme-provider";
import { ByteOpsLogoMark } from "@/lib/brand-icons";

export function TopBar() {
    const { resolvedTheme, setTheme, theme, mounted } = useTheme();

    const toggleTheme = () => {
        if (theme === "dark") setTheme("light");
        else if (theme === "light") setTheme("dark");
        else setTheme(resolvedTheme === "dark" ? "light" : "dark");
    };

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
