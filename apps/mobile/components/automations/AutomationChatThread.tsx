import { useRef, useState } from "react";
import { useWindowDimensions } from "react-native";
import type { FlashListRef } from "@shopify/flash-list";

import { AutomationComposer } from "@/components/automations/AutomationComposer";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { SkeletonChatBubbles } from "@/components/SkeletonLoader";
import { StateView } from "@/components/StateView";
import { useAutomationChat } from "@/hooks/useAutomationChat";
import { useChatMessageList } from "@/hooks/useChatMessageList";
import type { Message } from "@/lib/api";
import { useTranslation } from "react-i18next";

/** Live, replyable thread for one automation's dedicated chat — reuses the
 * same streaming engine + row rendering as the main chat screen
 * (`useChat` via `useAutomationChat`, `ChatMessageList` /
 * `useChatMessageList`), but with its own thin composer instead of the
 * full `ChatComposer` (no attach/voice/live-talk/math keyboard here). */
export function AutomationChatThread({
  chatId,
  isCurrent,
}: {
  chatId: string;
  isCurrent: () => boolean;
}) {
  const { t } = useTranslation();
  const { height: windowHeight } = useWindowDimensions();
  const listRef = useRef<FlashListRef<Message>>(null);
  const [input, setInput] = useState("");
  const {
    messages,
    streaming,
    finalizing,
    sendingMessageId,
    sendMessage,
    regenerateResponse,
    stopGeneration,
    handleFeedback,
    loading,
    loadError,
  } = useAutomationChat(chatId, isCurrent);
  const [, setMenuVisible] = useState(false);

  const { renderItem } = useChatMessageList({
    messages,
    streaming,
    finalizing,
    selectedModel: "smart-chat",
    highlightedMessageId: null,
    sendingMessageId,
    setMenuVisible,
    regenerateResponse,
    handleFeedback,
  });

  const handleSend = () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    sendMessage(text);
  };

  if (loadError) {
    return <StateView variant="error" title={t("common.error")} />;
  }

  return (
    <>
      {loading && messages.length === 0 ? (
        <SkeletonChatBubbles />
      ) : (
        <ChatMessageList
          listRef={listRef}
          messages={messages}
          headerInset={0}
          listBottomPad={16}
          hasMoreOlder={false}
          loadingOlder={false}
          chatLoading={false}
          routeChatId={chatId}
          emptyHeight={windowHeight * 0.4}
          renderItem={renderItem}
          onLoadOlder={() => {}}
          onScroll={() => {}}
          onScrollEnd={() => {}}
          onSelectStarter={() => {}}
          hideHomeStarters
          streamActive={streaming}
        />
      )}
      <AutomationComposer
        value={input}
        onChangeValue={setInput}
        onSend={handleSend}
        onStop={stopGeneration}
        streaming={streaming}
      />
    </>
  );
}
