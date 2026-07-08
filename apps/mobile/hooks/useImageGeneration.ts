import { useCallback, useState } from "react";
import { Alert } from "react-native";
import { useRouter } from "expo-router";

import { api } from "@/lib/api";
import { parseApiErrorDetail, resolveChatError } from "@/lib/chatErrorMessage";

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
  t: (key: string) => string;
};

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
  t,
}: Options) {
  const [promptOpen, setPromptOpen] = useState(false);
  const [generating, setGenerating] = useState(false);

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
      if (isOffline) {
        Alert.alert(t("chat.offline_title"), t("chat.offline_body"));
        return;
      }
      setGenerating(true);
      try {
        const activeChatId = await ensureChatId();
        if (!activeChatId) {
          Alert.alert(t("chat.error_title"), t("chat.error_generic"));
          return;
        }
        const result = await api.generateImage(token, {
          chat_id: activeChatId,
          prompt,
        });
        setMessages((prev) => [...prev, result.user_message, result.assistant_message]);
        newMessageCountRef.current += 2;
        setPromptOpen(false);
        onScrollToLatest();
      } catch (error) {
        const message = error instanceof Error ? error.message : t("common.error");
        const parsed = parseApiErrorDetail(message) ?? message;
        if (parsed.toLowerCase().includes("pro")) {
          onOpenUpgrade();
          return;
        }
        const resolved = resolveChatError({ message, isPro, t });
        if (resolved.kind === "quota") {
          Alert.alert(t("chat.error_title"), resolved.message);
          return;
        }
        Alert.alert(t("chat.error_title"), resolved.message);
      } finally {
        setGenerating(false);
      }
    },
    [
      token,
      generating,
      streaming,
      isOffline,
      ensureChatId,
      setMessages,
      newMessageCountRef,
      onScrollToLatest,
      isPro,
      onOpenUpgrade,
      t,
    ],
  );

  return {
    promptOpen,
    setPromptOpen,
    generating,
    openPrompt,
    submitPrompt,
  };
}
