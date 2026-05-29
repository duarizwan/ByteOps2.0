import { SignIn } from "@clerk/nextjs";
import { Sparkles } from "lucide-react";
import Link from "next/link";

const FEATURES = [
    "Summarize emails and surface what matters most",
    "Manage your calendar with natural language",
    "Track GitHub PRs, issues, and code activity",
    "Stay on top of JIRA tickets and sprints",
];

const TOOL_CHIPS = ["Gmail", "Calendar", "Slack", "GitHub", "JIRA", "Trello"];

export default function SignInPage() {
    return (
        <div className="flex min-h-screen">
            {/* ── Left Hero ─────────────────────────────────────────── */}
            <div
                className="hidden lg:flex w-[52%] flex-col justify-between p-12 flex-shrink-0 relative overflow-hidden"
                style={{
                    background: "linear-gradient(160deg, hsl(222, 84%, 2%) 0%, hsl(220, 60%, 10%) 100%)",
                }}
            >
                {/* Ambient glows */}
                <div className="pointer-events-none absolute -top-16 -right-16 w-64 h-64 rounded-full"
                    style={{ background: "radial-gradient(circle, rgba(37,99,235,0.13) 0%, transparent 70%)" }} />
                <div className="pointer-events-none absolute -bottom-12 left-10 w-52 h-52 rounded-full"
                    style={{ background: "radial-gradient(circle, rgba(99,102,241,0.09) 0%, transparent 70%)" }} />

                {/* Logo — consistent gradient + Sparkles icon */}
                <div className="relative z-10 flex items-center gap-3">
                    <div
                        className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                        style={{ background: "linear-gradient(135deg, #1d4ed8, #3b82f6)" }}
                    >
                        <Sparkles className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-white text-lg font-bold tracking-tight">ByteOps</span>
                </div>

                {/* Main copy — pushed down, filling the vertical space better */}
                <div className="relative z-10 space-y-8">
                    <div>
                        <h1 className="text-4xl font-extrabold text-white leading-tight tracking-tight mb-4"
                            style={{ letterSpacing: "-1px" }}>
                            Your AI-powered<br />work assistant
                        </h1>
                        <p className="text-[14px] leading-relaxed max-w-sm" style={{ color: "#94a3b8" }}>
                            Connect your tools. Chat with AI.<br />
                            Get more done — without the context switching.
                        </p>
                    </div>

                    {/* Feature list */}
                    <div className="space-y-3">
                        {FEATURES.map((feature, i) => (
                            <div key={i} className="flex items-start gap-3">
                                <div
                                    className="mt-0.5 w-[18px] h-[18px] rounded-full flex items-center justify-center flex-shrink-0"
                                    style={{
                                        background: "rgba(16,185,129,0.12)",
                                        border: "1px solid rgba(16,185,129,0.35)",
                                        boxShadow: "0 0 8px rgba(16,185,129,0.2)",
                                    }}
                                >
                                    <svg className="w-[9px] h-[9px]" fill="none" viewBox="0 0 24 24"
                                        stroke="#34d399" strokeWidth={3}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                    </svg>
                                </div>
                                <span className="text-[13px] leading-relaxed" style={{ color: "#94a3b8" }}>{feature}</span>
                            </div>
                        ))}
                    </div>

                    {/* Tool chips — more visible */}
                    <div>
                        <p className="text-[10px] uppercase tracking-widest font-semibold mb-3" style={{ color: "#334155" }}>
                            Works with
                        </p>
                        <div className="flex items-center gap-2 flex-wrap">
                            {TOOL_CHIPS.map((tool) => (
                                <div
                                    key={tool}
                                    className="px-3 py-1.5 rounded-lg text-[11px] font-medium"
                                    style={{
                                        background: "rgba(255,255,255,0.05)",
                                        border: "1px solid rgba(255,255,255,0.12)",
                                        color: "#64748b",
                                    }}
                                >
                                    {tool}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <p className="relative z-10 text-[11px]" style={{ color: "#1e3a5f" }}>
                    © 2026 ByteOps. All rights reserved.
                </p>
            </div>

            {/* ── Right Form ────────────────────────────────────────── */}
            <div className="flex-1 flex items-center justify-center px-8 py-12" style={{ background: "#f8fafc" }}>
                <div className="w-full max-w-sm">
                    {/* Mobile-only logo — consistent */}
                    <div className="flex lg:hidden items-center gap-3 mb-10">
                        <div
                            className="w-9 h-9 rounded-xl flex items-center justify-center"
                            style={{ background: "linear-gradient(135deg, #1d4ed8, #3b82f6)" }}
                        >
                            <Sparkles className="w-4 h-4 text-white" />
                        </div>
                        <span className="text-xl font-bold tracking-tight text-slate-900">ByteOps</span>
                    </div>

                    {/* Light gray card container */}
                    <div
                        className="rounded-2xl px-8 py-8"
                        style={{
                            background: "#f1f5f9",
                            border: "1px solid #e2e8f0",
                        }}
                    >
                        <h2 className="text-[22px] font-bold text-slate-900 tracking-tight mb-1 text-center"
                            style={{ letterSpacing: "-0.4px" }}>
                            Welcome back
                        </h2>
                        <p className="text-[13px] text-slate-500 mb-7 leading-relaxed text-center">
                            Sign in to your ByteOps workspace
                        </p>

                    <SignIn
                            fallbackRedirectUrl="/dashboard"
                            appearance={{
                                variables: {
                                    colorPrimary: "hsl(221.2, 83.2%, 53.3%)",
                                    colorBackground: "#f1f5f9",
                                    colorInputBackground: "#ffffff",
                                    colorInputText: "#0f172a",
                                    borderRadius: "0.625rem",
                                    fontFamily: "'Inter', system-ui, sans-serif",
                                    fontSize: "14px",
                                },
                                elements: {
                                    rootBox: "w-full mx-auto",
                                    cardBox: "shadow-none border-none bg-transparent w-full",
                                    card: "shadow-none p-0 bg-transparent w-full",
                                    header: "hidden",
                                    socialButtonsBlockButton:
                                        "border border-slate-200 bg-white hover:bg-slate-100 text-slate-800 transition-colors rounded-[0.625rem]",
                                    socialButtonsBlockButtonText: "text-slate-800 font-medium text-sm",
                                    dividerLine: "bg-slate-300",
                                    dividerText: "text-slate-400 text-xs",
                                    formFieldLabel: "text-[12px] font-medium text-slate-700",
                                    formFieldInput:
                                        "border border-slate-200 bg-white text-slate-900 rounded-[0.625rem]",
                                    formButtonPrimary:
                                        "bg-blue-600 hover:bg-blue-700 text-white rounded-[0.625rem] font-semibold transition-colors shadow-none",
                                    footerActionText: "text-slate-500 text-xs",
                                    footerActionLink: "text-blue-600 hover:text-blue-700 font-medium",
                                    identityPreviewEditButton: "text-blue-600",
                                    formResendCodeLink: "text-blue-600 hover:text-blue-700",
                                    alternativeMethodsBlockButton:
                                        "border border-slate-200 bg-white hover:bg-slate-100 text-slate-800 rounded-[0.625rem]",
                                },
                            }}
                        />
                    </div>{/* end light gray card */}

                    {/* Manual sign-up link — Clerk footer is hidden in globals.css */}
                    <p className="mt-5 text-center text-[13px] text-slate-500">
                        Don&apos;t have an account?{" "}
                        <Link
                            href="/sign-up"
                            className="font-semibold text-blue-600 hover:text-blue-700 transition-colors"
                        >
                            Sign up for free →
                        </Link>
                    </p>
                </div>
            </div>
        </div>
    );
}
