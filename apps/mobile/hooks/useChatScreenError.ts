import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ComposerSendDraft } from "@/lib/chat/chatSendLogic";
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
  const handleRejectedSendChange = useCallback((reason: "send_rejected" | "attachment_rejected" | null) => {
    if (reason) handleChatError("", reason);
    else setChatError((current) => current?.kind === "send_rejected" || current?.kind === "attachment_rejected" ? null : current);
  }, [handleChatError]);

  return {
    chatError,
    handleChatError,
    handleStreamBusy,
    dismissChatError,
    handleRejectedSendChange,
  };
}

/** Keep unsaved-send recovery separate from regeneration of a saved reply. */
export function useChatErrorRecovery({
  error, blocked, dismiss, retryRejectedSend, restoreRejectedAttachmentDraft,
  restoreComposerDraft, regenerate, selectedModel,
}: {
  error: ResolvedChatError | null;
  blocked: boolean;
  dismiss: () => void;
  retryRejectedSend: () => Promise<boolean>;
  restoreRejectedAttachmentDraft: (restore: (draft: ComposerSendDraft) => boolean) => boolean;
  restoreComposerDraft: (draft: ComposerSendDraft) => boolean;
  regenerate: (model: string) => unknown;
  selectedModel: string;
}) {
  return useCallback(() => {
    if (blocked) return;
    if (error?.kind === "attachment_rejected") {
      if (restoreRejectedAttachmentDraft(restoreComposerDraft)) dismiss();
      return;
    }
    if (error?.kind === "send_rejected") {
      dismiss();
      void retryRejectedSend();
      return;
    }
    if (error?.kind === "generic") {
      dismiss();
      void regenerate(selectedModel);
    }
  }, [blocked, error?.kind, dismiss, retryRejectedSend, restoreRejectedAttachmentDraft,
    restoreComposerDraft, regenerate, selectedModel]);
}

type StreamLifecycleParams = {
  streamActive: boolean;
  dismissChatError: () => void;
  token: string | null;
  isPro: boolean;
};

/** Clear inline errors while streaming and refresh quota after each turn. */
export function useChatStreamLifecycle({
  streamActive,
  dismissChatError,
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
    }
    prevStreamActiveRef.current = streamActive;
  }, [streamActive]);

  const quotaNudge = useQuotaNudge({ token, isPro, refreshKey: quotaRefreshKey });
  return { ...quotaNudge, turnRefreshKey: quotaRefreshKey };
}
