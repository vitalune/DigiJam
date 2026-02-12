"use client";

import { useConfig } from "@/contexts/config-context";
import { RecordingClient } from "./_components/RecordingClient";

export default function RecordingPage() {
  const { isHydrated } = useConfig();

  if (!isHydrated) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-[#232323] text-[#eeeeee]">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-[#d51bdb] border-t-transparent" />
      </main>
    );
  }

  return <RecordingClient />;
}
