import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { View } from "react-native";

import { ChatMessageRow } from "@/components/chat/ChatMessageRow";
import { StreamingChatMessageRow } from "@/components/chat/StreamingChatMessageRow";
import { SuggestionChips } from "@/components/SuggestionChips";
import type { Message, Suggestion } from "@/lib/api";
import {
  findLastAssistantId,
  findLastUserMessageId,
  isChatStreamActive,
  priorUserTextFor,
  streamVisualActiveForRow,
} from "@/lib/chatMessageLogic";
import { IMAGE_GEN_PENDING_ASSISTANT_ID } from "@/lib/imageGenIntent";
import { STREAM_LAYOUT_SETTLE_MS } from "@/lib/messageListLayout";

type Options = {
  messages: Message[];
  streaming: boolean;
  finalizing: boolean;
  selectedModel: string;
  highlightedMessageId: string | null;
  sendingMessageId: string | null;
  setMenuVisible: React.Dispatch<React.SetStateAction<boolean>>;
  regenerateResponse: (model: string) => void | Promise<void>;
  regenerating?: boolean;
  handleEditMessage: (message: Message) => void;
  handleFeedback: (messageId: string, next: "up" | "down" | null) => void;
  suggestions?: Suggestion[];
  onSelectSuggestion?: (prompt: string) => void;
  onDismissSuggestion?: (id: string) => void;
  lessonProjectId?: string | null;
  onOpenLesson?: (projectId: string) => void;
  imageGenerating?: boolean;
  onRetryImageGen?: () => void;
};

export function useChatMessageList({
  messages,
  streaming,
  finalizing,
  selectedModel,
  highlightedMessageId,
  sendingMessageId,
  setMenuVisible,
  regenerateResponse,
  regenerating = false,
  handleEditMessage,
  handleFeedback,
  suggestions = [],
  onSelectSuggestion,
  onDismissSuggestion,
  lessonProjectId = null,
  onOpenLesson,
  imageGenerating = false,
  onRetryImageGen,
}: Options) {
  useEffect(() => {
    if (messages.length === 0) setMenuVisible(false);
  }, [messages.length, setMenuVisible]);

  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const lastAssistantId = useMemo(
    () => findLastAssistantId(messages),
    [messages],
  );
  const lastUserMessageId = useMemo(
    () => findLastUserMessageId(messages),
    [messages],
  );

  const headerTitleLabel = null;

  // Defer inline suggestions until post-stream layout settle (avoids list bounce).
  const [suggestionsDelayed, setSuggestionsDelayed] = useState(false);
  useEffect(() => {
    if (streaming || finalizing) {
      setSuggestionsDelayed(true);
      return;
    }
    const timer = setTimeout(() => setSuggestionsDelayed(false), STREAM_LAYOUT_SETTLE_MS);
    return () => clearTimeout(timer);
  }, [streaming, finalizing]);

  const showSuggestions =
    !streaming &&
    !finalizing &&
    !imageGenerating &&
    !suggestionsDelayed &&
    suggestions.length > 0 &&
    Boolean(onSelectSuggestion) &&
    Boolean(onDismissSuggestion);

  const sharedRowProps = useMemo(
    () => ({
      lastAssistantId,
      selectedModel,
      highlightedMessageId,
      sendingMessageId,
      lastUserMessageId,
      onRegenerate: regenerateResponse,
      regenerating,
      onEdit: handleEditMessage,
      onFeedback: handleFeedback,
      lessonProjectId,
      onOpenLesson,
      onRetryImageGen,
    }),
    [
      lastAssistantId,
      selectedModel,
      highlightedMessageId,
      sendingMessageId,
      lastUserMessageId,
      regenerateResponse,
      regenerating,
      handleEditMessage,
      handleFeedback,
      lessonProjectId,
      onOpenLesson,
      onRetryImageGen,
    ],
  );

  // Read messages from a ref so feedback/refetch/done does not change
  // renderItem identity and force FlashList to revisit every visible row.
  const renderItem = useCallback(
    ({ item, index }: { item: Message; index: number }) => {
      const priorUserText = priorUserTextFor(messagesRef.current, index);

      if (item.id === "streaming" || item.id === IMAGE_GEN_PENDING_ASSISTANT_ID) {
        return (
          <StreamingChatMessageRow
            item={item}
            priorUserText={priorUserText}
            streamVisualActive={
              item.id === IMAGE_GEN_PENDING_ASSISTANT_ID
                ? true
                : isChatStreamActive(streaming, finalizing)
            }
            imageGenPending={item.id === IMAGE_GEN_PENDING_ASSISTANT_ID}
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
