import { useCallback, useRef, useState } from "react";
import { Alert } from "react-native";
import { useRouter } from "expo-router";

import { api } from "@/lib/api";
import { ApiRequestError } from "@/lib/api/client";
import { resolveChatError } from "@/lib/chatErrorMessage";
import { notifyWarning } from "@/lib/haptics";
import {
  IMAGE_GEN_FAILED_ASSISTANT_ID,
  IMAGE_GEN_PENDING_ASSISTANT_ID,
} from "@/lib/imageGenIntent";
import {
  applyImageGenFailure,
  hasImageGenFailedAssistant,
  imageGenUserBubble,
  restoreImageGenPending,
} from "@/lib/imageGenTurn";
import { notifyOfflineSendBlocked } from "@/lib/offlineSendFeedback";

type DraftChat = {
  prepareDraftChat: (
    projectId?: string | null,
    model?: string,
    quizMode?: import("@/lib/quizMode").QuizMode | null,
    opts?: { force?: boolean },
  ) => Promise<string | null>;
  skipLoadForChatIdRef: React.MutableRefObject<string | null>;
  draftChatIdRef: React.MutableRefObject<string | null>;
  setDraftChatId: React.Dispatch<React.SetStateAction<string | null>>;
  creatingRef: React.MutableRefObject<boolean>;
};

type Options = {
  token: string | null;
  chatId: string | null;
  setChatId: React.Dispatch<React.SetStateAction<string | null>>;
  setChatTitle: React.Dispatch<React.SetStateAction<string | null>>;
  setMessages: React.Dispatch<React.SetStateAction<import("@/lib/api").Message[]>>;
  draft: DraftChat;
  router: ReturnType<typeof useRouter>;
  selectedModel: string;
  streaming: boolean;
  isPro: boolean;
  isOffline: boolean;
  onOpenUpgrade: () => void;
  onOfflineBlocked?: () => void;
  onScrollToLatest: () => void;
  newMessageCountRef: React.MutableRefObject<number>;
  t: (key: string) => string;
};

export type ImageGenSubmit = {
  prompt: string;
  userMessage: string;
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
  isPro,
  isOffline,
  onOpenUpgrade,
  onOfflineBlocked,
  onScrollToLatest,
  newMessageCountRef,
  t,
}: Options) {
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

  const ensureChatId = useCallback(async (): Promise<string | null> => {
    if (chatId) return chatId;
    draft.creatingRef.current = true;
    try {
      const id = await draft.prepareDraftChat(undefined, selectedModel);
      if (!id) throw new Error("Could not create chat");
      draft.skipLoadForChatIdRef.current = id;
      setChatTitle(null);
      setChatId(id);
      draft.draftChatIdRef.current = null;
      draft.setDraftChatId(null);
      router.setParams({ chatId: id });
      return id;
    } finally {
      draft.creatingRef.current = false;
    }
  }, [chatId, draft, router, selectedModel, setChatId, setChatTitle]);

  const submitPrompt = useCallback(
    async (input: ImageGenSubmit) => {
      const authToken = tokenRef.current;
      if (!authToken) return;
      if (generatingRef.current) return;
      if (streamingRef.current) {
        Alert.alert(t("chat.error_title"), t("chat.busy"));
        return;
      }
      // Don't trust client isPro alone — try the API; HTTP 403 opens upgrade.
      if (isOffline) {
        notifyOfflineSendBlocked({
          warn: notifyWarning,
          showToast: onOfflineBlocked,
        });
        return;
      }
      const prompt = input.prompt.trim();
      const userContent = imageGenUserBubble(input.userMessage, prompt);
      if (!prompt || !userContent) return;

      lastSubmitRef.current = { prompt, userMessage: userContent };
      generatingRef.current = true;
      setGenerating(true);
      const abort = new AbortController();
      abortRef.current = abort;
      userCancelRef.current = false;

      const createdAt = new Date().toISOString();
      let addedOptimistic = false;
      setMessages((prev) => {
        const priorUserId = optimisticUserIdRef.current;
        const retrySameTurn =
          hasImageGenFailedAssistant(prev) &&
          Boolean(priorUserId) &&
          prev.some((row) => row.id === priorUserId && row.content === userContent);
        if (retrySameTurn) {
          return restoreImageGenPending(prev);
        }
        const without = prev.filter(
          (row) =>
            row.id !== IMAGE_GEN_FAILED_ASSISTANT_ID &&
            row.id !== IMAGE_GEN_PENDING_ASSISTANT_ID &&
            row.id !== priorUserId,
        );
        const optimisticUserId = `local-img-${Date.now()}`;
        optimisticUserIdRef.current = optimisticUserId;
        addedOptimistic = true;
        return [
          ...without,
          {
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
      if (addedOptimistic) {
        newMessageCountRef.current += 2;
      }
      onScrollToLatest();

      const optimisticUserId = optimisticUserIdRef.current;

      try {
        const activeChatId = await ensureChatId();
        if (!activeChatId) {
          setMessages((prev) => applyImageGenFailure(prev, "failed", t("chat.error_generic")));
          return;
        }
        const result = await api.generateImage(
          authToken,
          {
            chat_id: activeChatId,
            prompt,
            user_message: userContent,
          },
          { signal: abort.signal },
        );
        setMessages((prev) => {
          const without = prev.filter(
            (m) => m.id !== optimisticUserId && m.id !== IMAGE_GEN_PENDING_ASSISTANT_ID,
          );
          return [...without, result.user_message, result.assistant_message];
        });
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
        const resolved = resolveChatError({ message, isPro, t });
        setMessages((prev) => applyImageGenFailure(prev, "failed", resolved.message));
        if (resolved.kind === "quota") {
          Alert.alert(t("chat.error_title"), resolved.message);
        }
      } finally {
        if (abortRef.current === abort) abortRef.current = null;
        generatingRef.current = false;
        setGenerating(false);
      }
    },
    [
      isPro,
      isOffline,
      onOfflineBlocked,
      ensureChatId,
      setMessages,
      newMessageCountRef,
      onScrollToLatest,
      onOpenUpgrade,
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
