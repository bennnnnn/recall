import { useCallback, useState } from "react";
import { Alert } from "react-native";
import { useRouter } from "expo-router";

import { api } from "@/lib/api";
import { MESSAGE_PAGE_SIZE } from "@/lib/chatConstants";
import { writeCachedChatMessages } from "@/lib/chatMessageCache";
import { parseApiErrorDetail, resolveChatError } from "@/lib/chatErrorMessage";

const USER_MESSAGE_PREFIX = "Generate image: ";
const IMAGE_GEN_TIMEOUT_MS = 125_000;

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
  onScrollToLatest: () => void;
  newMessageCountRef: React.MutableRefObject<number>;
  blockMessageReloadRef: React.MutableRefObject<boolean>;
  t: (key: string) => string;
};

function buildOptimisticImageMessages(prompt: string, ts: number) {
  const createdAt = new Date(ts).toISOString();
  const userId = `local-imggen-user-${ts}`;
  const assistantId = `local-imggen-${ts}`;
  return {
    userId,
    assistantId,
    userMessage: {
      id: userId,
      role: "user" as const,
      content: `${USER_MESSAGE_PREFIX}${prompt}`,
      model: null,
      created_at: createdAt,
    },
    assistantMessage: {
      id: assistantId,
      role: "assistant" as const,
      content: "",
      model: null,
      created_at: createdAt,
      renderKey: assistantId,
    },
  };
}

function mergeImageGenerationResult(
  prev: import("@/lib/api").Message[],
  optimisticUserId: string,
  optimisticAssistantId: string,
  result: { user_message: import("@/lib/api").Message; assistant_message: import("@/lib/api").Message },
): import("@/lib/api").Message[] {
  const withoutOptimistic = prev.filter(
    (message) => message.id !== optimisticUserId && message.id !== optimisticAssistantId,
  );
  return [...withoutOptimistic, result.user_message, result.assistant_message];
}

function replaceAssistantWithError(
  prev: import("@/lib/api").Message[],
  assistantId: string,
  errorText: string,
): import("@/lib/api").Message[] {
  return prev.map((message) =>
    message.id === assistantId
      ? {
          ...message,
          content: errorText,
          renderKey: `${assistantId}-error`,
        }
      : message,
  );
}

function resolveImageGenErrorMessage(
  error: unknown,
  isPro: boolean,
  t: (key: string) => string,
): { message: string; openUpgrade: boolean; alertOnly: boolean } {
  const raw = error instanceof Error ? error.message : t("common.error");
  if (raw.includes("timed out") || raw.includes("AbortError")) {
    return { message: t("chat.image_gen_timeout"), openUpgrade: false, alertOnly: true };
  }
  const parsed = parseApiErrorDetail(raw) ?? raw;
  if (parsed.toLowerCase().includes("pro")) {
    return { message: parsed, openUpgrade: true, alertOnly: false };
  }
  const resolved = resolveChatError({ message: raw, isPro, t });
  if (resolved.kind === "quota") {
    return { message: resolved.message, openUpgrade: false, alertOnly: true };
  }
  const message =
    parsed.toLowerCase().includes("generate image") || parsed.toLowerCase().includes("could not generate")
      ? parsed
      : resolved.message;
  return { message, openUpgrade: false, alertOnly: false };
}

async function syncChatMessagesFromServer(
  token: string,
  activeChatId: string,
  setMessages: React.Dispatch<React.SetStateAction<import("@/lib/api").Message[]>>,
): Promise<void> {
  const page = await api.listMessages(token, activeChatId, { limit: MESSAGE_PAGE_SIZE });
  setMessages(page.messages);
  void writeCachedChatMessages(activeChatId, page.messages, page.has_more);
}

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
  onScrollToLatest,
  newMessageCountRef,
  blockMessageReloadRef,
  t,
}: Options) {
  const [promptOpen, setPromptOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [pendingAssistantId, setPendingAssistantId] = useState<string | null>(null);

  const openPrompt = useCallback(() => {
    if (!token || streaming || generating) return;
    if (!isPro) {
      onOpenUpgrade();
      return;
    }
    setPromptOpen(true);
  }, [token, streaming, generating, isPro, onOpenUpgrade]);

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
    async (prompt: string) => {
      if (!token || generating || streaming) return;
      if (!isPro) {
        onOpenUpgrade();
        return;
      }
      if (isOffline) {
        Alert.alert(t("chat.offline_title"), t("chat.offline_body"));
        return;
      }

      const trimmed = prompt.trim();
      if (!trimmed) return;

      const ts = Date.now();
      const optimistic = buildOptimisticImageMessages(trimmed, ts);
      let activeChatId: string | null = null;
      const abort = new AbortController();
      const abortTimer = setTimeout(() => abort.abort(), IMAGE_GEN_TIMEOUT_MS);

      setPromptOpen(false);
      setGenerating(true);
      blockMessageReloadRef.current = true;

      try {
        activeChatId = await ensureChatId();
        if (!activeChatId) {
          throw new Error(t("chat.error_generic"));
        }
        draft.skipLoadForChatIdRef.current = activeChatId;

        setPendingAssistantId(optimistic.assistantId);
        setMessages((prev) => [...prev, optimistic.userMessage, optimistic.assistantMessage]);
        newMessageCountRef.current += 2;
        onScrollToLatest();

        const result = await api.generateImage(
          token,
          {
            chat_id: activeChatId,
            prompt: trimmed,
          },
          abort.signal,
        );

        setPendingAssistantId(null);
        setGenerating(false);
        setMessages((prev) =>
          mergeImageGenerationResult(prev, optimistic.userId, optimistic.assistantId, result),
        );
        onScrollToLatest();
        void syncChatMessagesFromServer(token, activeChatId, setMessages)
          .then(() => onScrollToLatest())
          .catch(() => {});
      } catch (error) {
        const { message, openUpgrade, alertOnly } = resolveImageGenErrorMessage(error, isPro, t);
        setPendingAssistantId(null);
        setGenerating(false);
        setMessages((prev) =>
          replaceAssistantWithError(prev, optimistic.assistantId, message),
        );
        if (openUpgrade) {
          onOpenUpgrade();
        } else if (alertOnly) {
          Alert.alert(t("chat.error_title"), message);
        }
      } finally {
        clearTimeout(abortTimer);
        setGenerating(false);
        setPendingAssistantId(null);
        blockMessageReloadRef.current = false;
      }
    },
    [
      token,
      generating,
      streaming,
      isOffline,
      isPro,
      ensureChatId,
      draft,
      setMessages,
      newMessageCountRef,
      onScrollToLatest,
      onOpenUpgrade,
      blockMessageReloadRef,
      t,
    ],
  );

  return {
    promptOpen,
    setPromptOpen,
    generating,
    pendingAssistantId,
    openPrompt,
    submitPrompt,
  };
}
