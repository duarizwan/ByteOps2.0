import { useState, useEffect, useCallback } from "react";

const INTERVAL_MS = 1800;

export function useRotatingLabel(
    isActive: boolean,
    poolSize: number,
): [number, () => void] {
    const [idx, setIdx] = useState(0);

    useEffect(() => {
        if (!isActive) {
            setIdx(0);
            return;
        }
        const id = setInterval(() => {
            setIdx(i => (i + 1) % poolSize);
        }, INTERVAL_MS);
        return () => clearInterval(id);
    }, [isActive, poolSize]);

    const reset = useCallback(() => setIdx(0), []);
    return [idx, reset];
}
