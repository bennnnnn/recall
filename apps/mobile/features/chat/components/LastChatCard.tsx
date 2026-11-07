/**
 * The home's one way back in: the chat the user was last in, its title and when it was last
 * active, at the bottom above the composer; its words are only for a screen reader. A tap opens it as the drawer would. Read from the drawer's
 * cached list, so it costs no request and shows nothing until that list is in.
 */
import { useMemo, useSyncExternalStore } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useTranslation } from "react-i18next";

import { getCachedChatList, subscribeChatList } from "@/features/chat/model/chatListCache";
import { lastChat } from "@/features/chat/model/lastChat";
import { formatDate } from "@/lib/datetime/format";
import { tap } from "@/lib/haptics";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

const DAY_MS = 24 * 60 * 60 * 1000;

/** "3:05 PM" today, "Yesterday", else "Sep 8", in the user's zone. */
function whenLabel(at: string, yesterday: string, now: Date = new Date()): string {
  const date = new Date(at);
  const day = (d: Date) => formatDate(d, "monthDayYear");
  if (day(date) === day(now)) return formatDate(date, "time");
  if (day(date) === day(new Date(now.getTime() - DAY_MS))) return yesterday;
  return formatDate(date, "monthDay");
}

export function LastChatCard() {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const router = useRouter();
  const { chatId } = useLocalSearchParams<{ chatId?: string }>();
  const list = useSyncExternalStore(subscribeChatList, getCachedChatList, getCachedChatList);
  const chat = useMemo(() => lastChat(list, typeof chatId === "string" ? chatId : null), [list, chatId]);
  if (!chat) return null;

  return (
    <View style={s.wrap}>
      <Pressable
        style={({ pressed }) => [s.card, pressed && s.pressed]}
        onPress={() => {
          tap();
          router.setParams({ chatId: chat.id, highlightMessage: undefined });
        }}
        accessibilityRole="button"
        accessibilityLabel={`${t("chat.home.continue")}: ${chat.title}`}
        testID="home-last-chat"
      >
        <Icon name="message" size={IconSize.xs} color={theme.primary} />
        <Text style={s.title} numberOfLines={1}>
          {chat.title}
        </Text>
        <Text style={s.when}>{whenLabel(chat.updated_at, t("drawer.yesterday"))}</Text>
        <Icon name="chevron-right" size={IconSize.xs} color={theme.textTertiary} />
      </Pressable>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: { gap: Space.xxs, marginTop: "auto", paddingBottom: Space.xs },
    card: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      borderRadius: Radius.full,
      backgroundColor: theme.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      paddingHorizontal: Space.md,
      paddingVertical: Space.xs + 2,
    },
    pressed: { opacity: 0.85 },
    title: { ...Type.secondary, ...Weight.semibold, color: theme.text, flex: 1 },
    when: { ...Type.caption, color: theme.textSecondary },
  });
}
