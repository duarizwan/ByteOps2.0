"use client";

import type { FilterTab } from "@/lib/action-center-types";

const TABS: { value: FilterTab; label: string }[] = [
    { value: "all",     label: "All"     },
    { value: "pending", label: "Pending" },
    { value: "failed",  label: "Failed"  },
];

interface FilterTabsProps {
    active: FilterTab;
    onChange: (tab: FilterTab) => void;
}

export function FilterTabs({ active, onChange }: FilterTabsProps) {
    return (
        <div style={{ display: "flex", gap: 2 }}>
            {TABS.map(({ value, label }) => {
                const isActive = active === value;
                return (
                    <button
                        key={value}
                        role="button"
                        aria-label={label}
                        aria-selected={isActive}
                        onClick={() => onChange(value)}
                        style={{
                            padding: "4px 10px",
                            fontSize: 12,
                            fontWeight: isActive ? 600 : 400,
                            borderRadius: 6,
                            border: isActive
                                ? "1px solid color-mix(in srgb, var(--primary) 40%, transparent)"
                                : "1px solid transparent",
                            background: isActive
                                ? "color-mix(in srgb, var(--primary) 10%, transparent)"
                                : "transparent",
                            color: isActive ? "var(--primary)" : "var(--muted-foreground)",
                            cursor: "pointer",
                            transition: "all 0.12s",
                        }}
                    >
                        {label}
                    </button>
                );
            })}
        </div>
    );
}
