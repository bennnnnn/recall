import { memo, ReactElement, RefObject, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import { FlashList, FlashListRef, ListRenderItemInfo } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";

import { HomeStarters } from "@/features/home/components/HomeStarters";
import { LastChatCard } from "@/features/chat/components/LastChatCard";
import type { ChatListScroll } from "@/features/chat/hooks/useChatScroll";
import { useWarmMathRenderer } from "@/features/chat/hooks/useWarmMathRenderer";
import { useComposerDraftActivity } from "@/features/chat/context/ComposerDraftContext";
import { SkeletonChatBubbles } from "@/ui/feedback/SkeletonLoader";
import { Message } from "@/lib/api";
import {
  CHAT_RECYCLE_POOL,
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
  /** A window around a search hit ends before the newest message: its next page. */
  newerPage?: { loading: boolean; load: () => Promise<void> } | null;
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
  /**
   * Live talk's call is drawn over the thread, under the header: a screen reader skips the
   * messages it covers, as it skips a page under a sheet.
   */
  covered?: boolean;
};

/** What the list draws beyond the screen, and how many rows it keeps off it for reuse. */
const LIST_WINDOW = { drawDistance: 280, maxItemsInRecyclePool: CHAT_RECYCLE_POOL } as const;

/** FlashList never scrolls to the bottom on its own: useChatScroll is the one writer. */
const NO_AUTOSCROLL = -1;

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
  scroll,
  header,
  footer,
  covered = false,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  useWarmMathRenderer(messages);
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
        {...LIST_WINDOW}
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
        accessibilityElementsHidden={covered}
        importantForAccessibility={covered ? "no-hide-descendants" : "auto"}
        ListHeaderComponent={
          hasMoreOlder ? (
            <PageButton label={t("chat.load_earlier")} loadingLabel={t("chat.loading_earlier")}
              loading={loadingOlder} onPress={onLoadOlder} styles={s} />
          ) : null
        }
        ListFooterComponent={
          newerPage || footer ? (
            <>
              {newerPage ? (
                <PageButton label={t("chat.load_newer")} loadingLabel={t("chat.loading_newer")}
                  loading={newerPage.loading} onPress={() => void newerPage.load()} styles={s} />
              ) : null}
              {footer}
            </>
          ) : null
        }
        ListEmptyComponent={
          chatLoading && routeChatId ? (
            <View style={[s.empty, { height: emptyHeight }]}>
              <SkeletonChatBubbles />
            </View>
          ) : (
            <View style={[s.empty, { height: emptyHeight }]}>
              <HomeStarters composerActive={composerActive} footer={<LastChatCard />} />
            </View>
          )
        }
      />

      {header}
    </View>
  );
}

export const ChatMessageList = memo(ChatMessageListComponent);

/**
 * Load earlier (or newer) messages. While the page loads it says so, with a spinner, and a
 * screen reader hears it busy: it showed "…" and kept its old name.
 */
function PageButton({
  label,
  loadingLabel,
  loading,
  onPress,
  styles: s,
}: {
  label: string;
  loadingLabel: string;
  loading: boolean;
  onPress: () => void;
  styles: ReturnType<typeof makeStyles>;
}) {
  const theme = useTheme();
  const shown = loading ? loadingLabel : label;
  return (
    <Pressable
      style={s.loadEarlier}
      hitSlop={{ top: 5, bottom: 5 }}
      onPress={onPress}
      disabled={loading}
      accessibilityRole="button"
      accessibilityLabel={shown}
      accessibilityState={{ busy: loading, disabled: loading }}
    >
      {loading ? <ActivityIndicator size="small" color={theme.primary} /> : null}
      <Text style={s.loadEarlierText}>{shown}</Text>
    </Pressable>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    messagesArea: { flex: 1 },
    list: { flex: 1 },
    listHidden: { flex: 1, opacity: 0 },
    listContent: { paddingVertical: Space.xs },
    loadEarlier: {
      alignSelf: "center",
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
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
