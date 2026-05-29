"use client";

import { useEffect, useRef } from "react";

export function CursorGlow() {
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        let raf: number;
        let tx = -9999, ty = -9999;
        let cx = -9999, cy = -9999;

        const onMove = (e: MouseEvent) => {
            tx = e.clientX;
            ty = e.clientY;
        };

        const tick = () => {
            cx += (tx - cx) * 0.1;
            cy += (ty - cy) * 0.1;
            if (ref.current) {
                ref.current.style.transform = `translate(${cx - 250}px, ${cy - 250}px)`;
            }
            raf = requestAnimationFrame(tick);
        };

        window.addEventListener("mousemove", onMove, { passive: true });
        raf = requestAnimationFrame(tick);
        return () => {
            window.removeEventListener("mousemove", onMove);
            cancelAnimationFrame(raf);
        };
    }, []);

    return (
        <div
            ref={ref}
            className="pointer-events-none fixed z-[1] w-[500px] h-[500px] rounded-full will-change-transform"
            style={{
                top: 0,
                left: 0,
                background:
                    "radial-gradient(circle, rgba(59,130,246,0.11) 0%, rgba(139,92,246,0.05) 45%, transparent 70%)",
                filter: "blur(24px)",
            }}
        />
    );
}
