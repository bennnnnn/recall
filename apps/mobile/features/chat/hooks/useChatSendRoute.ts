import { useCallback, type MutableRefObject } from "react";

import { useComposerDraftApi } from "@/contexts/ComposerDraftContext";
import { useActionFeedbackOptional } from "@/contexts/ActionFeedbackContext";
import type { SendTurn } from "@/features/chat/hooks/useRestoreFailedSend";
import type { SendTurnStart } from "@/features/chat/hooks/useTurnStart";
import { uploadSendAttachment } from "@/features/chat/hooks/useSendAttachment";
import { buildPendingSendAfterCreate, type SendMessageOptions } from "@/features/chat/model/sendLogic";
import { resolveSendIntercept, type SendIntercept } from "@/features/chat/model/sendIntercept";
import { shouldRestoreFailedSend } from "@/features/chat/model/composerThreadDraft";
import { attachmentErrorMessage } from "@/features/attachments/model/attachmentErrors";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import { flushEmailDrafts } from "@/features/drafts/model/emailDraftFlush";
import type { ImageGenSubmit } from "@/features/images/hooks/useImageGeneration";
import { resolveClientGeoForQuery } from "@/lib/resolveClientGeoForQuery";
import type { Message, User } from "@/lib/api";

/** A send whose bubble, and typing dots when they could go up, are on screen. */
export type PaintedSend = SendTurn & {
  optimisticId: string;
  /** Whether the dots that went up with the bubble are still this send's; null when none did. */
  dotsCurrent: (() => boolean) | null;
  /** The composer view at the tap; a new chat's send is dropped if the view moves on first. */
  version: number;
};

type SendPhase = "idle" | "uploading" | "creating";
type PendingChatSend = ReturnType<typeof buildPendingSendAfterCreate>;

type Options = {
  token: string | null;
  chatId: string | null;
  messages: Message[];
  selectedModel: string;
  imageGenerating: boolean;
  onGenerateImage?: (request: ImageGenSubmit) => void;
  sendMessage: (text: string, opts?: SendMessageOptions) => void;
  sendStart: SendTurnStart;
  updateUser: (patch: Partial<User>) => Promise<void>;
  t: (key: string, options?: Record<string, unknown>) => string;
  pendingAttachmentRef: MutableRefObject<PendingAttachment | null>;
  setPendingAttachment: (value: PendingAttachment | null) => void;
  setPendingOutboundId: (id: string | null) => void;
  sendInFlightRef: MutableRefObject<boolean>;
  setSendPhase: (phase: SendPhase) => void;
  /** Takes the bubble back and returns the draft to the thread it was typed in. */
  restoreFailedSend: (turn: SendTurn, optimisticId: string, attached: PendingAttachment | null) => void;
  /** A send for a chat that does not exist yet: it creates one and waits for its id. */
  sendToNewChat: (send: PaintedSend, pending: PendingChatSend, giveBack: () => void) => Promise<void>;
};

/**
 * Where a send goes once its bubble is painted: the server reads whether it is a
 * picture (POST /images/intent) while the bubble is already up, then a picture is
 * handed to image generation under that bubble, and anything else goes to chat
 * once its location, file and drafts are ready. A send made while the last reply
 * only saves (after its `stream_end`) does all that at once and goes out after
 * that reply's `done`. A send stopped on the way takes its bubble and dots back
 * and returns the draft, so nothing is lost or left behind.
 */
export function useChatSendRoute({
  token,
  chatId,
  messages,
  selectedModel,
  imageGenerating,
  onGenerateImage,
  sendMessage,
  sendStart,
  updateUser,
  t,
  pendingAttachmentRef,
  setPendingAttachment,
  setPendingOutboundId,
  sendInFlightRef,
  setSendPhase,
  restoreFailedSend,
  sendToNewChat,
}: Options) {
  const { setInput, inputRef, stashFailedDraftForThread, getThreadKey } = useComposerDraftApi();
  const feedback = useActionFeedbackOptional();

  /** A picture is drawn under the painted bubble; a request that fails to save comes back to the composer. */
  const handToImageGeneration = useCallback(
    (intercept: Extract<SendIntercept, { kind: "generate" }>, send: PaintedSend, drafts: Promise<boolean>) => {
      const restoreImageDraft = () => {
        if (!send.isCurrentSession()) return;
        if (!send.isCurrentView() || getThreadKey() !== send.threadKey) {
          stashFailedDraftForThread(send.threadKey, send.composerText);
          return;
        }
        if (!pendingAttachmentRef.current && shouldRestoreFailedSend(inputRef.current, send.composerText)) {
          setInput(send.composerText);
          setPendingAttachment(send.attachment);
          return;
        }
        feedback?.error(t("chat.restore_draft_blocked"));
      };
      sendStart.cancelDots();
      onGenerateImage?.({
        prompt: intercept.prompt,
        userMessage: send.text,
        aspectRatio: null,
        referenceAttachment: intercept.reference?.attachment,
        referenceAttachmentIds: intercept.reference?.ids,
        persistenceReady: drafts,
        onPersistenceFailure: restoreImageDraft,
        userMessageId: send.optimisticId,
      });
      setPendingOutboundId(null);
      sendInFlightRef.current = false;
      setSendPhase("idle");
    },
    [
      getThreadKey, stashFailedDraftForThread, pendingAttachmentRef, inputRef, setInput, setPendingAttachment,
      feedback, t, sendStart, onGenerateImage, setPendingOutboundId, sendInFlightRef, setSendPhase,
    ],
  );

  return useCallback(
    async (send: PaintedSend) => {
      const drafts = flushEmailDrafts();
      // No dots could go up while the last reply saves: hand over after its `done`.
      const replySettled = send.dotsCurrent ? null : sendStart.whenReplySettled(send.optimisticId);
      let attached = send.attachment;
      const giveBack = () => {
        sendStart.cancelDots();
        restoreFailedSend(send, send.optimisticId, attached);
      };
      const stillSending = () => send.isCurrentView() && (send.dotsCurrent?.() ?? true);

      const deciding = resolveSendIntercept({
        text: send.text,
        attachment: attached,
        chatId,
        messages,
        canGenerate: Boolean(onGenerateImage),
        imageGenerating,
        token,
        isCurrentView: send.isCurrentView,
      });
      const intercept = deciding instanceof Promise ? await deciding : deciding;
      if (intercept.kind === "drop" || intercept.kind === "stale" || !stillSending()) return giveBack();
      if (intercept.kind === "generate") {
        await replySettled;
        if (!stillSending()) return giveBack();
        return handToImageGeneration(intercept, send, drafts);
      }

      const authToken = token;
      if (!authToken) return giveBack();
      const geo = await resolveClientGeoForQuery(authToken, send.text, t, updateUser);
      if (!geo.ok || !stillSending()) return giveBack();
      let attachmentIds: string[] | undefined;
      if (attached) {
        setSendPhase("uploading");
        try {
          ({ ids: attachmentIds, attachment: attached } = await uploadSendAttachment(authToken, attached));
        } catch (error) {
          giveBack();
          if (send.isCurrentView()) feedback?.error(attachmentErrorMessage(error, t));
          return;
        }
      }
      if (!(await drafts)) return giveBack();
      await replySettled;
      if (!stillSending()) return giveBack();

      const pending = buildPendingSendAfterCreate({
        text: send.text,
        composerText: send.composerText,
        attached,
        attachmentIds,
        optimisticId: send.optimisticId,
        clientGeo: geo.clientGeo,
        model: selectedModel,
      });
      if (!chatId) return sendToNewChat(send, pending, giveBack);
      sendMessage(pending.text, pending);
      setPendingOutboundId(null);
      sendInFlightRef.current = false;
      setSendPhase("idle");
    },
    [
      chatId, messages, onGenerateImage, imageGenerating, token, sendStart, restoreFailedSend,
      handToImageGeneration, t, updateUser, setSendPhase, feedback, selectedModel, sendToNewChat, sendMessage,
      setPendingOutboundId, sendInFlightRef,
    ],
  );
}
