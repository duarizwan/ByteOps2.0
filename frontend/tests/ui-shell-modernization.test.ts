import { readFileSync } from "fs";
import { resolve } from "path";

const dashboardSource = readFileSync(
    resolve(__dirname, "../src/app/dashboard/page.tsx"),
    "utf8"
);
const settingsSource = readFileSync(
    resolve(__dirname, "../src/app/settings/page.tsx"),
    "utf8"
);
const landingSource = readFileSync(
    resolve(__dirname, "../src/app/page.tsx"),
    "utf8"
);

describe("modern UI shell requirements", () => {
    it("dashboard shell has a small-screen layout path", () => {
        expect(dashboardSource).toContain("lg:");
        expect(dashboardSource).toContain("max-lg:");
    });

    it("settings shell has a small-screen layout path", () => {
        expect(settingsSource).toContain("lg:");
        expect(settingsSource).toContain("max-lg:");
    });

    it("landing page shows a product preview instead of only abstract decoration", () => {
        expect(landingSource).toContain("Dashboard preview");
        expect(landingSource).toContain("Workflow trace");
    });
});
