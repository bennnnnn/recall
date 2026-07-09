import { useCallback, useEffect, useMemo } from "react";
import { View } from "react-native";

import { ChatMessageRow } from "@/components/chat/ChatMessageRow";
import { StreamingChatMessageRow } from "@/components/chat/StreamingChatMessageRow";
import { SuggestionChips } from "@/components/SuggestionChips";
import type { Message, Suggestion } from "@/lib/api";
import {
  findLastAssistantId,
  isChatStreamActive,
  priorUserTextFor,
  streamVisualActiveForRow,
} from "@/lib/chatMessageLogic";

type Options = {
  messages: Message[];
  streaming: boolean;
  finalizing: boolean;
  selectedModel: string;
  quizLanguage: string;
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
  setMenuVisible: React.Dispatch<React.SetStateAction<boolean>>;
  regenerateResponse: (model: string) => void | Promise<void>;
  handleEditMessage: (message: Message) => void;
  handleFeedback: (messageId: string, next: "up" | "down" | null) => void;
  suggestions?: Suggestion[];
  onSelectSuggestion?: (prompt: string) => void;
  onDismissSuggestion?: (id: string) => void;
};

export function useChatMessageList({
  messages,
  streaming,
  finalizing,
  selectedModel,
  quizLanguage,
  highlightedMessageId,
  sendingMessageId,
  setMenuVisible,
  regenerateResponse,
  handleEditMessage,
  handleFeedback,
  suggestions = [],
  onSelectSuggestion,
  onDismissSuggestion,
}: Options) {
  useEffect(() => {
    if (messages.length === 0) setMenuVisible(false);
  }, [messages.length, setMenuVisible]);

  const lastAssistantId = useMemo(
    () => findLastAssistantId(messages),
    [messages],
  );

  const headerTitleLabel = null;
  const showSuggestions =
    !streaming &&
    !finalizing &&
    suggestions.length > 0 &&
    Boolean(onSelectSuggestion) &&
    Boolean(onDismissSuggestion);

  const sharedRowProps = useMemo(
    () => ({
      lastAssistantId,
      selectedModel,
      quizLanguage,
      highlightedMessageId,
      sendingMessageId,
      onRegenerate: regenerateResponse,
      onEdit: handleEditMessage,
      onFeedback: handleFeedback,
    }),
    [
      lastAssistantId,
      selectedModel,
      quizLanguage,
      highlightedMessageId,
      sendingMessageId,
      regenerateResponse,
      handleEditMessage,
      handleFeedback,
    ],
  );

  const renderItem = useCallback(
    ({ item, index }: { item: Message; index: number }) => {
      const priorUserText = priorUserTextFor(messages, index);

      if (item.id === "streaming") {
        return (
          <StreamingChatMessageRow
            item={item}
            priorUserText={priorUserText}
            streamVisualActive={isChatStreamActive(streaming, finalizing)}
            {...sharedRowProps}
          />
        );
      }

      const streamVisualActive = streamVisualActiveForRow(
        item.role,
        item.id,
        lastAssistantId,
        streaming,
        finalizing,
      );
      const row = (
        <ChatMessageRow
          item={item}
          priorUserText={priorUserText}
          streamVisualActive={streamVisualActive}
          {...sharedRowProps}
        />
      );

      if (
        showSuggestions &&
        item.role === "assistant" &&
        item.id === lastAssistantId &&
        onSelectSuggestion &&
        onDismissSuggestion
      ) {
        return (
          <View>
            {row}
            <SuggestionChips
              suggestions={suggestions}
              onSelect={onSelectSuggestion}
              onDismiss={onDismissSuggestion}
            />
          </View>
        );
      }

      return row;
    },
    [
      sharedRowProps,
      messages,
      streaming,
      finalizing,
      lastAssistantId,
      showSuggestions,
      suggestions,
      onSelectSuggestion,
      onDismissSuggestion,
    ],
  );

  return { lastAssistantId, headerTitleLabel, renderItem };
}
