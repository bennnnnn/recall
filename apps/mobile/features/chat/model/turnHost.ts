import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { useRouter } from "expo-router";

import type { useDraftChat } from "@/features/chat/hooks/useDraftChat";
import type { Message } from "@/lib/api";

/**
 * What a turn started beside the plain send path (image generation, live
 * talk) takes from the open chat screen: the chat it lands in, how to create
 * one, and how to put its bubbles on screen.
 */
export type ChatTurnHost = {
  token: string | null;
  chatId: string | null;
  setChatId: Dispatch<SetStateAction<string | null>>;
  setChatTitle: Dispatch<SetStateAction<string | null>>;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  draft: ReturnType<typeof useDraftChat>;
  router: ReturnType<typeof useRouter>;
  selectedModel: string;
  isOffline: boolean;
  onScrollToLatest: () => void;
  newMessageCountRef: MutableRefObject<number>;
  t: (key: string) => string;
};
