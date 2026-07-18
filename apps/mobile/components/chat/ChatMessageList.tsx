import { memo, ReactElement, RefObject, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native";
import { FlashList, FlashListRef, ListRenderItemInfo } from "@shopify/flash-list";
import { useTranslation } from "react-i18next";

import { HomeStarters } from "@/components/HomeStarters";
import { SkeletonChatBubbles } from "@/components/SkeletonLoader";
import { Message } from "@/lib/api";
import {
  beginStreamLayoutHold,
  messageListItemType,
  messageListKey,
} from "@/lib/messageListLayout";
import { Theme, useTheme } from "@/lib/theme";

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
  onSelectStarter: (prompt: string) => void;
  header?: ReactElement | null;
  hideHomeStarters?: boolean;
  listFooter?: ReactElement | null;
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
  chatLoading,
  routeChatId,
  emptyHeight,
  renderItem,
  onLoadOlder,
  onScroll,
  onScrollEnd,
  onSelectStarter,
  header,
  hideHomeStarters = false,
  listFooter = null,
  streamActive = false,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const showFooterInEmpty = Boolean(listFooter && messages.length === 0);
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
  // That same fight reappears right as a stream ends: useChatScroll's own
  // post-stream scrollToEnd is deliberately deferred by STREAM_LAYOUT_SETTLE_MS
  // (matching MessageBubble's layout hold, which reveals full markdown +
  // feedback icons over that same window and grows the row's height). If
  // native autoscroll re-armed the instant `streamActive` flips false, it
  // would fire off the pre-growth height, then the deferred scrollToEnd (or
  // FlashList's own growth-triggered autoscroll) corrects again a moment
  // later — a visible "falls, then snaps back". Keep native autoscroll
  // suppressed through that settle window too, so the single deferred
  // scrollToEnd is the sole writer for this transition as well.
  const [autoscrollSuppressed, setAutoscrollSuppressed] = useState(streamActive);
  useEffect(() => {
    if (streamActive) {
      setAutoscrollSuppressed(true);
      return;
    }
    return beginStreamLayoutHold(setAutoscrollSuppressed);
  }, [streamActive]);

  const maintainVisibleContentPosition = useMemo(
    () =>
      autoscrollSuppressed
        ? {
            disabled: false,
            autoscrollToBottomThreshold: -1,
            startRenderingFromBottom: true,
          }
        : {
            disabled: false,
            autoscrollToBottomThreshold: 0.25,
            startRenderingFromBottom: true,
          },
    [autoscrollSuppressed],
  );

  return (
    <View style={s.messagesArea}>
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
          showFooterInEmpty ? (
            <View style={[s.empty, s.emptyWithFooter, { minHeight: emptyHeight }]}>
              {listFooter}
            </View>
          ) : listFooter ? null : chatLoading && routeChatId ? (
            <View style={[s.empty, { height: emptyHeight }]}>
              <SkeletonChatBubbles />
            </View>
          ) : hideHomeStarters ? (
            <View style={[s.empty, { height: emptyHeight }]} />
          ) : (
            <View style={[s.empty, { height: emptyHeight }]}>
              <HomeStarters onSelect={onSelectStarter} />
            </View>
          )
        }
        ListFooterComponent={
          messages.length > 0 && listFooter ? listFooter : undefined
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
    listContent: { paddingVertical: 8 },
    loadEarlier: {
      alignSelf: "center",
      marginVertical: 10,
      paddingHorizontal: 16,
      paddingVertical: 8,
      borderRadius: 999,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    loadEarlierText: { fontSize: 14, fontWeight: "600", color: theme.primary },
    empty: {
      flexGrow: 1,
      alignItems: "stretch",
      justifyContent: "flex-start",
      paddingTop: 4,
    },
    emptyWithFooter: {
      justifyContent: "flex-end",
      paddingBottom: 8,
    },
  });
}
