import { memo, ReactElement, RefObject, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native";
import { FlashList, FlashListRef, ListRenderItemInfo } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";

import { HomeStarters } from "@/features/home/components/HomeStarters";
import { useComposerDraftActivity } from "@/features/chat/context/ComposerDraftContext";
import { SkeletonChatBubbles } from "@/ui/feedback/SkeletonLoader";
import { Message } from "@/lib/api";
import {
  beginStreamLayoutHold,
  latchStartRenderingFromBottom,
  messageListItemType,
  messageListKey,
  STREAM_AUTOSCROLL_RESUME_MS,
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
  /** A window around a search hit ends before the newest message: its next page. */
  newerPage?: { loading: boolean; load: () => Promise<void> } | null;
  chatLoading: boolean;
  routeChatId?: string;
  emptyHeight: number;
  renderItem: (info: ListRenderItemInfo<Message>) => ReactElement | null;
  onLoadOlder: () => void;
  onScroll: (event: NativeSyntheticEvent<NativeScrollEvent>) => void;
  onScrollEnd: () => void;
  onContentSizeChange?: (width: number, height: number) => void;
  onListLayout?: (height: number) => void;
  header?: ReactElement | null;
  /** When true, disable FlashList autoscroll — useChatScroll owns bottom-pinning. */
  streamActive?: boolean;
};

function ChatMessageListComponent({
  listRef,
  messages,
  headerInset,
  listBottomPad,
  hasMoreOlder,
  loadingOlder,
  newerPage = null,
  chatLoading,
  routeChatId,
  emptyHeight,
  renderItem,
  onLoadOlder,
  onScroll,
  onScrollEnd,
  onContentSizeChange,
  onListLayout,
  header,
  streamActive = false,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const composerActive = useComposerDraftActivity();
  // Stable content-container style: the previous inline `{ paddingTop, paddingBottom }`
  // object was fresh every render, so FlashList re-laid out on every parent render
  // (including every composer keystroke). Memoize so it only changes when the
  // insets actually change.
  const contentContainerStyle = useMemo(
    () => [s.listContent, { paddingTop: headerInset, paddingBottom: listBottomPad }],
    [s.listContent, headerInset, listBottomPad],
  );
  // Two bottom-pin writers (FlashList autoscroll + JS scrollToEnd) fought at
  // LLM burst boundaries → jitter. While streaming, disable native autoscroll
  // (threshold < 0) and let useChatScroll own pinning exclusively.
  //
  // The same fight used to reappear at stream end: chrome unfreezes, chips
  // land, and native autoscroll re-armed on the same STREAM_LAYOUT_SETTLE_MS
  // tick as JS scrollToEnd — two writers, springy up/down. Keep native off
  // until STREAM_AUTOSCROLL_RESUME_MS so the deferred JS pin is the only
  // writer after the row has actually grown.
  const [autoscrollSuppressed, setAutoscrollSuppressed] = useState(streamActive);
  useEffect(() => {
    if (streamActive) {
      setAutoscrollSuppressed(true);
      return;
    }
    return beginStreamLayoutHold(setAutoscrollSuppressed, STREAM_AUTOSCROLL_RESUME_MS);
  }, [streamActive]);

  // Latched per chat: a value kept from earlier renders, adjusted while rendering.
  const [startLatch, setStartLatch] = useState({ chatKey: "", value: false });
  const chatKey = `${routeChatId ?? "new"}:${messages.length === 0 ? "empty" : "live"}`;
  const latched = latchStartRenderingFromBottom({
    chatKey,
    previousChatKey: startLatch.chatKey,
    previousValue: startLatch.value,
    messageCount: messages.length,
    hasMoreOlder,
  });
  if (latched.chatKey !== startLatch.chatKey || latched.value !== startLatch.value) setStartLatch(latched);
  const startFromBottom = latched.value;
  // In a window the bottom is not the newest message: a newer page must not pull
  // the list down past what the user is reading.
  const holdPosition = autoscrollSuppressed || newerPage != null;
  const maintainVisibleContentPosition = useMemo(
    () =>
      holdPosition
        ? {
            disabled: false,
            autoscrollToBottomThreshold: -1,
            startRenderingFromBottom: startFromBottom,
          }
        : {
            disabled: false,
            autoscrollToBottomThreshold: 0.25,
            startRenderingFromBottom: startFromBottom,
          },
    [holdPosition, startFromBottom],
  );

  return (
    <View
      style={s.messagesArea}
      onLayout={(event) => onListLayout?.(event.nativeEvent.layout.height)}
    >
      <FlashList
        ref={listRef}
        data={messages}
        style={s.list}
        drawDistance={280}
        maintainVisibleContentPosition={maintainVisibleContentPosition}
        keyExtractor={messageListKey}
        getItemType={messageListItemType}
        renderItem={renderItem}
        onScroll={onScroll}
        onScrollEndDrag={onScrollEnd}
        onMomentumScrollEnd={onScrollEnd}
        onContentSizeChange={onContentSizeChange}
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
        ListFooterComponent={
          newerPage ? (
            <Pressable
              style={s.loadEarlier}
              onPress={() => void newerPage.load()}
              disabled={newerPage.loading}
              accessibilityRole="button"
              accessibilityLabel={t("chat.load_newer")}
            >
              <Text style={s.loadEarlierText}>{newerPage.loading ? "…" : t("chat.load_newer")}</Text>
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
              <HomeStarters composerActive={composerActive} />
            </View>
          )
        }
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
