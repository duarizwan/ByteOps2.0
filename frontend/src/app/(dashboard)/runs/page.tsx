import "react";
import { Suspense } from "react";
import "@xyflow/react/dist/style.css";
import { ActionCenter } from "@/components/runs/action-center";
import { Loader2 } from "lucide-react";

export const metadata = { title: "Execution Trace — ByteOps" };

export default function RunsRoute() {
    return (
        <div
            className="h-screen flex flex-col overflow-hidden"
            style={{ background: "var(--background)" }}
        >
            <Suspense
                fallback={
                    <div className="flex-1 flex items-center justify-center">
                        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                    </div>
                }
            >
                <ActionCenter />
            </Suspense>
        </div>
    );
}
