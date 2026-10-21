import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ComposerSendDraft } from "@/features/chat/model/sendLogic";
import { resolveChatError, type ResolvedChatError } from "@/features/chat/model/errorMessage";

export function useChatErrorHandlers(isPaid: boolean) {
  const { t } = useTranslation();
  const [chatError, setChatError] = useState<ResolvedChatError | null>(null);

  const handleChatError = useCallback(
    (message: string, code?: string) => {
      setChatError(resolveChatError({ message, code, isPaid, t }));
    },
    [isPaid, t],
  );

  const handleStreamBusy = useCallback(() => {
    setChatError(resolveChatError({ message: "", code: "busy", isPaid, t }));
  }, [isPaid, t]);

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

/** Clear the inline error once a reply starts streaming. */
export function useDismissErrorWhileStreaming(streamActive: boolean, dismissChatError: () => void) {
  useEffect(() => {
    if (streamActive) dismissChatError();
  }, [streamActive, dismissChatError]);
}
