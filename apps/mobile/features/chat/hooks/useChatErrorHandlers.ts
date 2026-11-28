import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ComposerSendDraft } from "@/features/chat/model/sendLogic";
import { resolveChatError, type ResolvedChatError } from "@/features/chat/model/errorMessage";
import { forgetChatIfGone } from "@/features/chat/model/chatGone";
import { api } from "@/lib/api";
import { getSessionGeneration } from "@/lib/auth";
import { useLatestRef } from "@/lib/latestRef";

/** The stream's code for a turn whose chat, or whose message to answer, the server has not. */
const NOT_FOUND_CODE = "not_found";

/**
 * A turn refused as not found: its chat may be gone (deleted on another device), or only the
 * message a regenerate answers. The chat is read to tell them apart; a gone one goes
 * (`forgetChatIfGone`), and the screen gives way to New chat.
 */
async function checkChatGone(token: string, chatId: string): Promise<void> {
  const session = getSessionGeneration();
  try {
    await api.getChat(token, chatId);
  } catch (error) {
    if (session === getSessionGeneration()) forgetChatIfGone(chatId, error);
  }
}

export function useChatErrorHandlers(isPaid: boolean, open?: { token: string | null; chatId: string | null }) {
  const { t } = useTranslation();
  const [chatError, setChatError] = useState<ResolvedChatError | null>(null);
  const openRef = useLatestRef(open);

  const handleChatError = useCallback(
    (message: string, code?: string, cause?: string) => {
      setChatError(resolveChatError({ message, code, isPaid, t }));
      const { token, chatId } = openRef.current ?? {};
      // An unsaved send is reported as its retry; `cause` is the server's own code.
      if ((cause ?? code) === NOT_FOUND_CODE && token && chatId) void checkChatGone(token, chatId);
    },
    [isPaid, t, openRef],
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
};

/** Clear the inline error once a reply starts streaming, and the busy notice once only its save is left. */
export function useChatStreamLifecycle({
  streamActive,
  replySaving,
  dismissChatError,
  dismissBusyNotice,
}: StreamLifecycleParams) {
  useEffect(() => {
    if (streamActive) dismissChatError();
  }, [streamActive, dismissChatError]);

  // Its Stop would cut the save short and mark a whole reply stopped.
  useEffect(() => {
    if (replySaving) dismissBusyNotice();
  }, [replySaving, dismissBusyNotice]);
}
