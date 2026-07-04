import React, { createContext, useContext } from "react";

import type { StreamingDraft } from "@/hooks/useChat";

const StreamingDraftContext = createContext<StreamingDraft | null>(null);

export function StreamingDraftProvider({
  value,
  children,
}: {
  value: StreamingDraft | null;
  children: React.ReactNode;
}) {
  return (
    <StreamingDraftContext.Provider value={value}>{children}</StreamingDraftContext.Provider>
  );
}

export function useStreamingDraft(): StreamingDraft | null {
  return useContext(StreamingDraftContext);
}
