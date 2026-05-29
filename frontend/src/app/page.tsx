import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Zap, Shield, Workflow, Brain } from "lucide-react";
import { ByteOpsLogoMark } from "@/lib/brand-icons";
import { CursorGlow } from "@/components/cursor-glow";

const CARDS = [
    {
        num: "01",
        Icon: Workflow,
        rgb: "6,182,212",
        title: "Cross-Tool Automation",
        body: "One command drafts the reply, opens the ticket, and pings Slack — all at once.",
    },
    {
        num: "02",
        Icon: Brain,
        rgb: "139,92,246",
        title: "Always in Context",
        body: "Your AI remembers every email, ticket, and meeting. No repeated context, ever.",
    },
    {
        num: "03",
        Icon: Shield,
        rgb: "16,185,129",
        title: "Secure by Default",
        body: "OAuth2 per tool. Scoped, revocable access. Your data never leaves your control.",
    },
];

export default async function HomePage() {
    const { userId } = await auth();
    if (userId) redirect("/dashboard");

    return (
        <div className="min-h-screen flex flex-col overflow-hidden" style={{ background: "hsl(222, 84%, 2%)" }}>

            {/* Cursor glow — client component */}
            <CursorGlow />

            {/* Grid */}
            <div
                className="pointer-events-none fixed inset-0 z-0"
                style={{
                    backgroundImage: `
            linear-gradient(rgba(37,99,235,0.09) 1px, transparent 1px),
            linear-gradient(90deg, rgba(37,99,235,0.09) 1px, transparent 1px)
          `,
                    backgroundSize: "44px 44px",
                    maskImage: "radial-gradient(ellipse 110% 70% at 50% 0%, black 10%, transparent 100%)",
                    WebkitMaskImage: "radial-gradient(ellipse 110% 70% at 50% 0%, black 10%, transparent 100%)",
                }}
            />

            {/* Central top glow */}
            <div
                className="pointer-events-none fixed top-[-220px] left-1/2 -translate-x-1/2 w-[900px] h-[520px] z-0"
                style={{ background: "radial-gradient(ellipse at center, rgba(37,99,235,0.22) 0%, transparent 70%)" }}
            />

            {/* Floating orbs */}
            <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
                <div
                    className="orb-float absolute top-[12%] left-[6%] w-72 h-72 rounded-full"
                    style={{ background: "radial-gradient(circle, rgba(139,92,246,0.07) 0%, transparent 70%)", filter: "blur(48px)", animationDelay: "0s" }}
                />
                <div
                    className="orb-float absolute top-[55%] right-[8%] w-56 h-56 rounded-full"
                    style={{ background: "radial-gradient(circle, rgba(6,182,212,0.06) 0%, transparent 70%)", filter: "blur(40px)", animationDelay: "4s" }}
                />
                <div
                    className="orb-float absolute bottom-[8%] left-[28%] w-48 h-48 rounded-full"
                    style={{ background: "radial-gradient(circle, rgba(37,99,235,0.08) 0%, transparent 70%)", filter: "blur(36px)", animationDelay: "8s" }}
                />
            </div>

            {/* ── Nav ── */}
            <nav className="relative z-10 h-16 flex items-center justify-between px-8 border-b border-white/[0.05] backdrop-blur-sm">
                <div className="flex items-center gap-3">
                    <div
                        className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                        style={{ background: "linear-gradient(135deg, #1d4ed8, #3b82f6)" }}
                    >
                        <ByteOpsLogoMark className="w-4 h-5" />
                    </div>
                    <span className="text-white text-lg font-bold tracking-tight">ByteOps</span>
                </div>
                <Link
                    href="/sign-up"
                    className="group flex items-center gap-2 text-sm font-semibold text-white px-5 py-2 rounded-xl transition-all duration-200 hover:brightness-110 hover:shadow-[0_0_20px_rgba(59,130,246,0.45)]"
                    style={{ background: "linear-gradient(135deg, #1d4ed8, #3b82f6)" }}
                >
                    Get Started
                    <ArrowRight className="w-4 h-4 transition-transform duration-200 group-hover:translate-x-0.5" />
                </Link>
            </nav>

            {/* ── Hero ── */}
            <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 text-center pt-12 pb-28">

                {/* Badge */}
                <div
                    className="anim-fade-up anim-delay-1 inline-flex items-center gap-2 text-xs font-medium px-4 py-1.5 rounded-full mb-8 border"
                    style={{ background: "rgba(37,99,235,0.1)", borderColor: "rgba(37,99,235,0.3)", color: "#93c5fd" }}
                >
                    <Zap className="w-3.5 h-3.5" />
                    AI-powered workspace
                </div>

                {/* Headline */}
                <h1
                    className="anim-fade-up anim-delay-2 font-extrabold leading-[1.05] text-white mb-5"
                    style={{ fontSize: "clamp(44px, 7vw, 72px)", letterSpacing: "-2.5px" }}
                >
                    One Dashboard.
                    <br />
                    <span className="text-gradient-primary">All Your Tools.</span>
                </h1>

                {/* Subtext */}
                <p
                    className="anim-fade-up anim-delay-3 text-base leading-relaxed max-w-md mx-auto mb-10"
                    style={{ color: "#94a3b8" }}
                >
                    ByteOps AI connects Gmail, Slack, JIRA, GitHub and more —
                    <br />
                    then handles the work so you don&apos;t have to.
                </p>

                {/* CTA */}
                <div className="anim-fade-up anim-delay-4 flex flex-col items-center gap-4 mb-20">
                    <Link
                        href="/sign-up"
                        className="group inline-flex items-center gap-2 text-sm font-bold text-white px-8 py-3.5 rounded-xl transition-all duration-200 hover:brightness-110 hover:shadow-[0_0_36px_rgba(59,130,246,0.55)]"
                        style={{ background: "linear-gradient(135deg, #1d4ed8, #3b82f6)" }}
                    >
                        Start for Free
                        <ArrowRight className="w-4 h-4 transition-transform duration-200 group-hover:translate-x-1" />
                    </Link>
                    <Link
                        href="/sign-in"
                        className="text-sm font-medium transition-colors duration-200 hover:text-white"
                        style={{ color: "#64748b" }}
                    >
                        Already have an account?{" "}
                        <span className="font-semibold" style={{ color: "#60a5fa" }}>Sign in →</span>
                    </Link>
                </div>

                {/* ── Feature Cards ── */}
                <div className="anim-fade-up anim-delay-5 grid grid-cols-1 md:grid-cols-3 gap-5 max-w-4xl mx-auto w-full">
                    {CARDS.map(({ num, Icon, rgb, title, body }) => (
                        <div
                            key={num}
                            className="group relative p-6 rounded-2xl text-left transition-all duration-500 hover:-translate-y-2 cursor-default overflow-hidden"
                            style={{
                                background: "rgba(255,255,255,0.025)",
                                border: "1px solid rgba(255,255,255,0.07)",
                            }}
                        >
                            {/* Top accent line */}
                            <div
                                className="absolute top-0 left-0 right-0 h-px opacity-30 group-hover:opacity-100 transition-opacity duration-500"
                                style={{ background: `linear-gradient(90deg, transparent, rgba(${rgb},0.9), transparent)` }}
                            />

                            {/* Hover bg tint */}
                            <div
                                className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                                style={{ background: `radial-gradient(ellipse at 25% 25%, rgba(${rgb},0.08) 0%, transparent 65%)` }}
                            />

                            {/* Watermark number */}
                            <div
                                className="absolute top-4 right-5 text-[80px] font-black leading-none select-none pointer-events-none"
                                style={{ color: `rgba(${rgb},0.07)` }}
                            >
                                {num}
                            </div>

                            {/* Icon */}
                            <div
                                className="relative w-10 h-10 rounded-xl flex items-center justify-center mb-5"
                                style={{
                                    background: `rgba(${rgb},0.1)`,
                                    border: `1px solid rgba(${rgb},0.28)`,
                                    boxShadow: `0 0 18px rgba(${rgb},0.22), 0 0 36px rgba(${rgb},0.08)`,
                                }}
                            >
                                <Icon className="w-5 h-5" style={{ color: `rgb(${rgb})` }} />
                            </div>

                            {/* Step label */}
                            <p
                                className="text-[10px] font-semibold uppercase tracking-[0.14em] mb-1.5"
                                style={{ color: `rgba(${rgb},0.6)` }}
                            >
                                {num}
                            </p>

                            <h3 className="font-semibold text-white text-[15px] mb-2.5">{title}</h3>
                            <p className="text-sm leading-relaxed" style={{ color: "#64748b" }}>{body}</p>

                            {/* Bottom glow line */}
                            <div
                                className="absolute bottom-0 left-8 right-8 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                                style={{ background: `linear-gradient(90deg, transparent, rgba(${rgb},0.6), transparent)` }}
                            />
                        </div>
                    ))}
                </div>

                <p className="mt-16 text-[11px]" style={{ color: "#1e3a5f" }}>
                    © 2026 ByteOps. All rights reserved.
                </p>
            </main>
        </div>
    );
}
