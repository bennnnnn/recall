import { useCallback, useRef, useState } from "react";

import { useActionFeedbackOptional } from "@/contexts/actionFeedbackCore";
import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api/client";
import { resolveChatError } from "@/features/chat/model/errorMessage";
import { notifyWarning } from "@/lib/haptics";
import { reportRecoverableError } from "@/lib/reportRecoverableError";
import {
  IMAGE_GEN_FAILED_ASSISTANT_ID,
  IMAGE_GEN_PENDING_ASSISTANT_ID,
} from "@/features/images/model/imageGenMessages";
import {
  applyImageGenFailure,
  hasImageGenFailedAssistant,
  imageGenUserBubble,
  restoreImageGenPending,
} from "@/features/images/model/imageGenTurn";
import { notifyOfflineSendBlocked } from "@/lib/offlineSendFeedback";
import { invalidateGalleryCache } from "@/features/attachments/model/galleryListCache";
import type { PendingAttachment } from "@/features/attachments/model/attachments";
import { useEnsureChatId } from "@/features/chat/hooks/useEnsureChatId";
import { uploadSendAttachment } from "@/features/chat/hooks/useSendAttachment";
import type { ChatTurnHost } from "@/features/chat/model/turnHost";

type Options = ChatTurnHost & {
  streaming: boolean;
  isPaid: boolean;
  onOpenUpgrade: () => void;
  onOfflineBlocked?: () => void;
};

export type ImageGenSubmit = {
  prompt: string;
  userMessage: string;
  aspectRatio?: string | null;
  referenceAttachmentIds?: string[];
  referenceAttachment?: PendingAttachment;
  /** Already-running persistence gate; optimistic image UI does not wait on it. */
  persistenceReady?: Promise<boolean>;
  /** Restores the composer draft when the persistence gate rejects the turn. */
  onPersistenceFailure?: () => void;
  /**
   * The composer already painted this request's bubble: the picture is drawn
   * under it, and a request that cannot start takes it away and restores the draft.
   */
  userMessageId?: string;
};

/** Pro image generation from composer text — no confirmation sheet. */
export function useImageGeneration({
  token,
  chatId,
  setChatId,
  setChatTitle,
  setMessages,
  draft,
  router,
  selectedModel,
  streaming,
  isPaid,
  isOffline,
  onOpenUpgrade,
  onOfflineBlocked,
  onScrollToLatest,
  newMessageCountRef,
  t,
}: Options) {
  const feedback = useActionFeedbackOptional();
  const [generating, setGenerating] = useState(false);
  // Refs so submitPrompt never no-ops on a stale streaming/generating closure
  // from a prior Fast Refresh or a turn that just finished.
  const generatingRef = useRef(false);
  const streamingRef = useRef(streaming);
  const tokenRef = useRef(token);
  const abortRef = useRef<AbortController | null>(null);
  const userCancelRef = useRef(false);
  const lastSubmitRef = useRef<ImageGenSubmit | null>(null);
  const optimisticUserIdRef = useRef<string | null>(null);
  generatingRef.current = generating;
  streamingRef.current = streaming;
  tokenRef.current = token;

  const ensureChatId = useEnsureChatId({ chatId, selectedModel, draft, setChatId, setChatTitle, router });

  const submitPrompt = useCallback(
    async (input: ImageGenSubmit) => {
      const adoptedId = input.userMessageId;
      /** A painted bubble with nothing to draw under it goes, and its draft comes back. */
      const giveBack = () => {
        if (!adoptedId) return;
        setMessages((prev) => prev.filter((row) => row.id !== adoptedId));
        newMessageCountRef.current = Math.max(0, newMessageCountRef.current - 1);
        input.onPersistenceFailure?.();
      };
      const authToken = tokenRef.current;
      if (!authToken || generatingRef.current) return giveBack();
      // The composer hands over its own painted turn only once no reply streams.
      if (streamingRef.current && !adoptedId) {
        reportRecoverableError(feedback, t("chat.busy"));
        return;
      }
      // Don't trust client isPaid alone — try the API; HTTP 403 opens upgrade.
      if (isOffline) {
        notifyOfflineSendBlocked({
          warn: notifyWarning,
          showToast: onOfflineBlocked,
        });
        return giveBack();
      }
      const prompt = input.prompt.trim();
      const userContent = imageGenUserBubble(input.userMessage, prompt);
      if (!prompt || !userContent) return giveBack();

      // A retry draws under the same bubble by its own path (`priorUserId`).
      lastSubmitRef.current = { ...input, prompt, userMessage: userContent, userMessageId: undefined };
      generatingRef.current = true;
      setGenerating(true);
      const abort = new AbortController();
      abortRef.current = abort;
      userCancelRef.current = false;

      const createdAt = new Date().toISOString();
      // React may defer/replay functional updates. Establish request identity
      // before scheduling the render, never from inside its updater.
      const priorUserId = optimisticUserIdRef.current;
      const optimisticUserId = adoptedId ?? priorUserId ?? `local-img-${Date.now()}`;
      optimisticUserIdRef.current = optimisticUserId;
      setMessages((prev) => {
        const retrySameTurn =
          !adoptedId &&
          hasImageGenFailedAssistant(prev) &&
          Boolean(priorUserId) &&
          prev.some((row) => row.id === priorUserId && row.content === userContent);
        if (retrySameTurn) {
          return restoreImageGenPending(prev);
        }
        const adopted = adoptedId ? prev.find((row) => row.id === adoptedId) : undefined;
        const without = prev.filter(
          (row) =>
            row.id !== IMAGE_GEN_FAILED_ASSISTANT_ID &&
            row.id !== IMAGE_GEN_PENDING_ASSISTANT_ID &&
            row.id !== priorUserId &&
            row.id !== adoptedId,
        );
        return [
          ...without,
          adopted ? { ...adopted, content: userContent } : {
            id: optimisticUserId,
            role: "user",
            content: userContent,
            model: null,
            created_at: createdAt,
          },
          {
            id: IMAGE_GEN_PENDING_ASSISTANT_ID,
            role: "assistant",
            content: "",
            model: "image-gen-model",
            created_at: createdAt,
          },
        ];
      });
      // The composer counted its own bubble when it painted it.
      const addedRows = adoptedId ? 1 : priorUserId ? 0 : 2;
      newMessageCountRef.current += addedRows;
      onScrollToLatest();

      try {
        const persistenceReady = input.persistenceReady
          ? await input.persistenceReady.catch(() => false)
          : true;
        if (!persistenceReady) {
          setMessages((prev) =>
            prev.filter(
              (row) =>
                row.id !== optimisticUserId &&
                row.id !== IMAGE_GEN_PENDING_ASSISTANT_ID,
            ),
          );
          if (adoptedId || !priorUserId) {
            newMessageCountRef.current = Math.max(
              0,
              newMessageCountRef.current - 2,
            );
          }
          optimisticUserIdRef.current = null;
          lastSubmitRef.current = null;
          input.onPersistenceFailure?.();
          return;
        }
        const persistedInput = {
          ...input,
          persistenceReady: undefined,
          onPersistenceFailure: undefined,
          userMessageId: undefined,
        };
        lastSubmitRef.current = persistedInput;

        const activeChatId = await ensureChatId();
        if (!activeChatId) {
          setMessages((prev) => applyImageGenFailure(prev, "failed", t("chat.error_generic")));
          return;
        }
        const referenceIds = input.referenceAttachment
          ? (await uploadSendAttachment(authToken, input.referenceAttachment)).ids
          : input.referenceAttachmentIds;
        // Retry the same upload/reference, not whatever image is newest later.
        lastSubmitRef.current = {
          ...persistedInput,
          referenceAttachment: undefined,
          referenceAttachmentIds: referenceIds,
        };
        if (abort.signal.aborted) throw new Error("Image request cancelled");
        const result = await api.generateImage(
          authToken,
          {
            chat_id: activeChatId,
            prompt,
            user_message: userContent,
            aspect_ratio: input.aspectRatio ?? null,
            reference_attachment_ids: referenceIds,
          },
          { signal: abort.signal },
        );
        if (abort.signal.aborted) throw new Error("Image request cancelled");
        setMessages((prev) => {
          const without = prev.filter(
            (m) => m.id !== optimisticUserId && m.id !== IMAGE_GEN_PENDING_ASSISTANT_ID,
          );
          return [...without, result.user_message, result.assistant_message];
        });
        invalidateGalleryCache();
        optimisticUserIdRef.current = null;
        lastSubmitRef.current = null;
        onScrollToLatest();
      } catch (error) {
        const canceled = userCancelRef.current;
        userCancelRef.current = false;
        if (canceled) {
          setMessages((prev) => applyImageGenFailure(prev, "canceled"));
          return;
        }
        if (error instanceof ApiRequestError && error.status === 403) {
          setMessages((prev) => applyImageGenFailure(prev, "failed"));
          onOpenUpgrade();
          return;
        }
        const message = error instanceof Error ? error.message : t("common.error");
        const resolved = resolveChatError({ message, isPaid, t });
        setMessages((prev) => applyImageGenFailure(prev, "failed", resolved.message));
      } finally {
        if (abortRef.current === abort) abortRef.current = null;
        generatingRef.current = false;
        setGenerating(false);
      }
    },
    [
      isPaid,
      isOffline,
      onOfflineBlocked,
      ensureChatId,
      setMessages,
      newMessageCountRef,
      onScrollToLatest,
      onOpenUpgrade,
      feedback,
      t,
    ],
  );

  const cancel = useCallback(() => {
    if (!generatingRef.current && !abortRef.current) return;
    userCancelRef.current = true;
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const retry = useCallback(() => {
    const last = lastSubmitRef.current;
    if (!last || generatingRef.current) return;
    void submitPrompt(last);
  }, [submitPrompt]);

  return {
    generating,
    submitPrompt,
    cancel,
    retry,
  };
}
