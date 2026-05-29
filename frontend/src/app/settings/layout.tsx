import type { Metadata } from "next";

export const metadata: Metadata = {
    title: "Settings — ByteOps",
    description: "Manage your connected tools and account preferences.",
};

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
    return children;
}
