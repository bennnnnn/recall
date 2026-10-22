import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAuthOptional } from "@/contexts/AuthContext";
import type { ComposerSendDraft } from "@/features/chat/model/sendLogic";
import { useQuotaNudge } from "@/features/chat/hooks/useQuotaNudge";
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
  /** "Still generating — tap Stop" is over once the reply's text is all in. */
  const dismissBusyNotice = useCallback(() => {
    setChatError((current) => (current?.kind === "busy" ? null : current));
  }, []);
  const handleRejectedSendChange = useCallback((reason: "send_rejected" | "attachment_rejected" | null) => {
    if (reason) handleChatError("", reason);
    else setChatError((current) => current?.kind === "send_rejected" || current?.kind === "attachment_rejected" ? null : current);
  }, [handleChatError]);

  return {
    chatError,
    handleChatError,
    handleStreamBusy,
    dismissChatError,
    dismissBusyNotice,
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
  /** The reply's text is all in (`stream_end`) and only its save is left. */
  replySaving: boolean;
  dismissChatError: () => void;
  dismissBusyNotice: () => void;
  token: string | null;
  isPaid: boolean;
};

/** Clear inline errors while streaming and refresh quota after each turn. */
export function useChatStreamLifecycle({
  streamActive,
  replySaving,
  dismissChatError,
  dismissBusyNotice,
  token,
  isPaid,
}: StreamLifecycleParams) {
  const [quotaRefreshKey, setQuotaRefreshKey] = useState(0);
  const prevStreamActiveRef = useRef(false);

  useEffect(() => {
    if (streamActive) dismissChatError();
  }, [streamActive, dismissChatError]);

  // Its Stop would cut the save short and mark a whole reply stopped.
  useEffect(() => {
    if (replySaving) dismissBusyNotice();
  }, [replySaving, dismissBusyNotice]);

  useEffect(() => {
    if (prevStreamActiveRef.current && !streamActive) {
      setQuotaRefreshKey((k) => k + 1);
    }
    prevStreamActiveRef.current = streamActive;
  }, [streamActive]);

  // A paid plan painted from the launch cache reads "free" until /auth/me answers.
  const planKnown = useAuthOptional()?.profileValidated ?? true;
  const quotaNudge = useQuotaNudge({ token, isPaid, planKnown, refreshKey: quotaRefreshKey });
  return quotaNudge;
}
