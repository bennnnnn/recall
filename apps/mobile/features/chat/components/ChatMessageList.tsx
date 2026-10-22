import { memo, ReactElement, RefObject, useMemo, useRef } from "react";
import { Pressable, StyleSheet, Text, View, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native";
import { FlashList, FlashListRef, ListRenderItemInfo } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";

import { HomeStarters } from "@/features/home/components/HomeStarters";
import type { ChatListScroll } from "@/features/chat/hooks/useChatScroll";
import { useWarmMathRenderer } from "@/features/chat/hooks/useWarmMathRenderer";
import { SkeletonChatBubbles } from "@/ui/feedback/SkeletonLoader";
import { Message } from "@/lib/api";
import {
  latchStartRenderingFromBottom,
  messageListItemType,
  messageListKey,
} from "@/lib/messageListLayout";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

type Props = {
  listRef: RefObject<FlashListRef<Message> | null>;
  messages: Message[];
  headerInset: number;
  listBottomPad: number;
  hasMoreOlder: boolean;
  loadingOlder: boolean;
  chatLoading: boolean;
  routeChatId?: string;
  emptyHeight: number;
  renderItem: (info: ListRenderItemInfo<Message>) => ReactElement | null;
  onLoadOlder: () => void;
  onScroll: (event: NativeSyntheticEvent<NativeScrollEvent>) => void;
  onScrollEnd: () => void;
  /** useChatScroll's wiring: it alone pins the list to the bottom. */
  scroll?: ChatListScroll;
  header?: ReactElement | null;
  /** After the last message, inside the scroll content (the keyboard spacer). */
  footer?: ReactElement | null;
};

/** FlashList never scrolls to the bottom on its own: useChatScroll is the one writer. */
const NO_AUTOSCROLL = -1;

function ChatMessageListComponent({
  listRef,
  messages,
  headerInset,
  listBottomPad,
  hasMoreOlder,
  loadingOlder,
  chatLoading,
  routeChatId,
  emptyHeight,
  renderItem,
  onLoadOlder,
  onScroll,
  onScrollEnd,
  scroll,
  header,
  footer,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  useWarmMathRenderer(messages);
  const s = useMemo(() => makeStyles(theme), [theme]);
  // Stable content-container style: the previous inline `{ paddingTop, paddingBottom }`
  // object was fresh every render, so FlashList re-laid out on every parent render
  // (including every composer keystroke). Memoize so it only changes when the
  // insets actually change.
  const contentContainerStyle = useMemo(
    () => [s.listContent, { paddingTop: headerInset, paddingBottom: listBottomPad }],
    [s.listContent, headerInset, listBottomPad],
  );
  const startFromBottomState = useRef({ chatKey: "", value: false });
  const chatKey = `${routeChatId ?? "new"}:${messages.length === 0 ? "empty" : "live"}`;
  startFromBottomState.current = latchStartRenderingFromBottom({
    chatKey,
    previousChatKey: startFromBottomState.current.chatKey,
    previousValue: startFromBottomState.current.value,
    messageCount: messages.length,
    hasMoreOlder,
  });
  const startFromBottom = startFromBottomState.current.value;
  const maintainVisibleContentPosition = useMemo(
    () => ({
      disabled: false,
      autoscrollToBottomThreshold: NO_AUTOSCROLL,
      startRenderingFromBottom: startFromBottom,
    }),
    [startFromBottom],
  );

  return (
    <View
      style={s.messagesArea}
      onLayout={(event) => scroll?.onListLayout(event.nativeEvent.layout.height)}
    >
      <FlashList
        ref={listRef}
        data={messages}
        // An opened chat is drawn once it sits at its end, never top-then-jump.
        style={scroll?.hidden ? s.listHidden : s.list}
        drawDistance={280}
        maintainVisibleContentPosition={maintainVisibleContentPosition}
        keyExtractor={messageListKey}
        getItemType={messageListItemType}
        renderItem={renderItem}
        onScroll={onScroll}
        onScrollBeginDrag={scroll?.onReaderScrollBegin}
        onMomentumScrollBegin={scroll?.onReaderScrollBegin}
        onScrollEndDrag={scroll?.onReaderScrollEndDrag ?? onScrollEnd}
        onMomentumScrollEnd={onScrollEnd}
        onContentSizeChange={scroll?.onContentSizeChange}
        onCommitLayoutEffect={scroll?.onLayoutCommit}
        scrollEventThrottle={16}
        contentContainerStyle={contentContainerStyle}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="interactive"
        ListHeaderComponent={
          hasMoreOlder ? (
            <Pressable
              style={s.loadEarlier}
              onPress={onLoadOlder}
              disabled={loadingOlder}
              accessibilityRole="button"
              accessibilityLabel={t("chat.load_earlier")}
            >
              <Text style={s.loadEarlierText}>
                {loadingOlder ? "…" : t("chat.load_earlier")}
              </Text>
            </Pressable>
          ) : null
        }
        ListEmptyComponent={
          chatLoading && routeChatId ? (
            <View style={[s.empty, { height: emptyHeight }]}>
              <SkeletonChatBubbles />
            </View>
          ) : (
            <View style={[s.empty, { height: emptyHeight }]}>
              <HomeStarters />
            </View>
          )
        }
        ListFooterComponent={footer}
      />

      {header}
    </View>
  );
}

export const ChatMessageList = memo(ChatMessageListComponent);

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    messagesArea: { flex: 1 },
    list: { flex: 1 },
    listHidden: { flex: 1, opacity: 0 },
    listContent: { paddingVertical: Space.xs },
    loadEarlier: {
      alignSelf: "center",
      marginVertical: Space.sm,
      paddingHorizontal: Space.md,
      paddingVertical: Space.xs,
      borderRadius: Radius.full,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    loadEarlierText: { ...Type.label, color: theme.primary },
    empty: {
      flexGrow: 1,
      alignItems: "stretch",
      justifyContent: "flex-start",
      paddingTop: Space.xxs,
    },
  });
}
