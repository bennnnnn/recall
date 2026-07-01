import { ReactElement, RefObject, useMemo } from "react";
import { Pressable, StyleSheet, Text, View, type NativeScrollEvent, type NativeSyntheticEvent } from "react-native";
import { FlashList, FlashListRef, ListRenderItemInfo } from "@shopify/flash-list";
import { LinearGradient } from "expo-linear-gradient";
import { useTranslation } from "react-i18next";

import { HomeStarters } from "@/components/HomeStarters";
import { StateView } from "@/components/StateView";
import { Message } from "@/lib/api";
import { ESTIMATED_MESSAGE_HEIGHT, messageListItemType } from "@/lib/messageListLayout";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  listRef: RefObject<FlashListRef<Message> | null>;
  messages: Message[];
  headerInset: number;
  listBottomPad: number;
  fadeHeight: number;
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
};

export function ChatMessageList({
  listRef,
  messages,
  headerInset,
  listBottomPad,
  fadeHeight,
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
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.messagesArea}>
      <FlashList
        ref={listRef}
        data={messages}
        style={s.list}
        drawDistance={280}
        maintainVisibleContentPosition={{
          disabled: false,
          autoscrollToBottomThreshold: 0.1,
          startRenderingFromBottom: true,
        }}
        keyExtractor={(item) => item.id}
        getItemType={messageListItemType}
        estimatedItemSize={ESTIMATED_MESSAGE_HEIGHT}
        renderItem={renderItem}
        onScroll={onScroll}
        onScrollEndDrag={onScrollEnd}
        onMomentumScrollEnd={onScrollEnd}
        scrollEventThrottle={16}
        contentContainerStyle={[
          s.listContent,
          { paddingTop: headerInset, paddingBottom: listBottomPad },
        ]}
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
              <StateView variant="loading" compact />
            </View>
          ) : (
            <View style={[s.empty, { height: emptyHeight }]}>
              <HomeStarters onSelect={onSelectStarter} />
            </View>
          )
        }
      />

      <LinearGradient
        colors={[theme.bg, theme.bg, `${theme.bg}00`]}
        locations={[0, 0.78, 1]}
        style={[s.headerFade, { height: fadeHeight }]}
        pointerEvents="none"
      />

      {header}
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    messagesArea: { flex: 1 },
    list: { flex: 1 },
    listContent: { paddingVertical: 8 },
    headerFade: {
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      zIndex: 50,
    },
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
      alignItems: "center",
      justifyContent: "center",
      paddingVertical: 16,
    },
  });
}
