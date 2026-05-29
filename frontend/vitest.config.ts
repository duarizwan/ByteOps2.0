import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
    plugins: [react()],
    test: {
        environment: "jsdom",
        globals: true,
        setupFiles: ["./tests/setup.ts"],
        server: {
            deps: {
                // react-markdown v10 is ESM-only and very heavy to transform in jsdom.
                // Externalising it avoids OOM during test runs.
                external: ["react-markdown"],
            },
        },
    },
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
});
