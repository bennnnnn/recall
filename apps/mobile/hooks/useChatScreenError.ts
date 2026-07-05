import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useQuotaNudge } from "@/hooks/useQuotaNudge";
import { resolveChatError, type ResolvedChatError } from "@/lib/chatErrorMessage";

export function useChatErrorHandlers(isPro: boolean) {
  const { t } = useTranslation();
  const [chatError, setChatError] = useState<ResolvedChatError | null>(null);

  const handleChatError = useCallback(
    (message: string, code?: string) => {
      setChatError(resolveChatError({ message, code, isPro, t }));
    },
    [isPro, t],
  );

  const handleStreamBusy = useCallback(() => {
    setChatError(resolveChatError({ message: "", code: "busy", isPro, t }));
  }, [isPro, t]);

  const dismissChatError = useCallback(() => setChatError(null), []);

  return {
    chatError,
    handleChatError,
    handleStreamBusy,
    dismissChatError,
  };
}

type StreamLifecycleParams = {
  streamActive: boolean;
  dismissChatError: () => void;
  refreshHome: (opts?: { silent?: boolean; force?: boolean }) => Promise<void>;
  token: string | null;
  isPro: boolean;
};

/** Clear inline errors while streaming and refresh quota/home after each turn. */
export function useChatStreamLifecycle({
  streamActive,
  dismissChatError,
  refreshHome,
  token,
  isPro,
}: StreamLifecycleParams) {
  const [quotaRefreshKey, setQuotaRefreshKey] = useState(0);
  const prevStreamActiveRef = useRef(false);

  useEffect(() => {
    if (streamActive) dismissChatError();
  }, [streamActive, dismissChatError]);

  useEffect(() => {
    if (prevStreamActiveRef.current && !streamActive) {
      setQuotaRefreshKey((k) => k + 1);
      void refreshHome({ silent: true, force: true });
    }
    prevStreamActiveRef.current = streamActive;
  }, [streamActive, refreshHome]);

  return useQuotaNudge({ token, isPro, refreshKey: quotaRefreshKey });
}
