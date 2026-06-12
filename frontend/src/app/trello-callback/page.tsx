"use client";

import { useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";

function TrelloCallbackInner() {
  const searchParams = useSearchParams();

  useEffect(() => {
    const nonce = searchParams.get("nonce");
    const hash = window.location.hash.slice(1);
    const token = new URLSearchParams(hash).get("token");
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    if (nonce && token) {
      window.location.href = `${apiBase}/api/auth/trello/callback/${encodeURIComponent(nonce)}?token=${encodeURIComponent(token)}`;
    } else {
      window.location.href = `/settings?error=trello_missing_token`;
    }
  }, [searchParams]);

  return (
    <div className="flex items-center justify-center h-screen">
      <p className="text-muted-foreground">Connecting Trello...</p>
    </div>
  );
}

export default function TrelloCallbackPage() {
  return (
    <Suspense>
      <TrelloCallbackInner />
    </Suspense>
  );
}
