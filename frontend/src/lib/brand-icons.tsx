/** ByteOps "B" logomark — exact SVG used on bytecorp.io */
export function ByteOpsLogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 22 35"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M10.8474 13.4283C8.31215 13.4283 5.97798 14.2657 4.13182 15.6658V0.30249H0V34.0857H4.13182V31.8482C5.97798 33.2481 8.31215 34.0857 10.8474 34.0857C16.8121 34.0857 21.6648 29.4522 21.6648 23.757C21.6648 18.0617 16.8121 13.4283 10.8474 13.4283ZM10.8474 30.2122C7.38282 30.2122 4.51907 27.7108 4.13182 24.5002V23.0137C4.51907 19.803 7.38282 17.3017 10.8474 17.3017C14.5753 17.3017 17.6082 20.1975 17.6082 23.757C17.6082 27.3164 14.5753 30.2122 10.8474 30.2122Z"
        fill="white"
      />
      <rect x="8.16699" y="2.39331" width="4.18852" height="4.18852" fill="white" />
    </svg>
  );
}

/**
 * Official brand icon CDN URLs for each connected tool.
 * Gmail and Calendar use gstatic official product logos.
 * Others use Google's favicon service at 64px.
 */
export const BRAND_ICON_URLS: Record<string, string> = {
  gmail:    "https://www.gstatic.com/images/branding/productlogos/gmail_2026/v2/web/192px.svg",
  calendar: "https://www.gstatic.com/images/branding/productlogos/calendar_2026/v2/web/192px.svg",
  slack:    "https://www.google.com/s2/favicons?domain=slack.com&sz=64",
  github:   "https://www.google.com/s2/favicons?domain=github.com&sz=64",
  jira:     "https://www.google.com/s2/favicons?domain=jira.atlassian.com&sz=64",
  trello:   "https://www.google.com/s2/favicons?domain=trello.com&sz=64",
  dropbox:  "https://www.google.com/s2/favicons?domain=dropbox.com&sz=64",
};

/** Returns the CDN URL for a tool's brand icon, or null if unknown. */
export function getBrandIconUrl(toolId: string): string | null {
  return BRAND_ICON_URLS[toolId.toLowerCase()] ?? null;
}

interface BrandIconImgProps {
  toolId: string;
  size?: number;
  className?: string;
  alt?: string;
}

/**
 * Renders a brand icon <img> for the given tool ID.
 * Returns null if the tool ID is unknown.
 */
export function BrandIconImg({ toolId, size = 20, className, alt }: BrandIconImgProps) {
  const url = getBrandIconUrl(toolId);
  if (!url) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={alt ?? toolId}
      width={size}
      height={size}
      className={className}
    />
  );
}
