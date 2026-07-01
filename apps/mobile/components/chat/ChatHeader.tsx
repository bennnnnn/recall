import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { HamburgerIcon } from "@/components/HamburgerIcon";
import { ReminderBadge } from "@/components/ReminderBadge";
import { tap } from "@/lib/haptics";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  paddingTop: number;
  height: number;
  menuOverlayOpen: boolean;
  headerTitleLabel: string | null;
  titleGenerating: boolean;
  chatTitle: string | null;
  showIndicator: boolean;
  unseenCount: number;
  hasMessages: boolean;
  onOpenDrawer: () => void;
  onOpenReminders: () => void;
  onNewChat: () => void;
  onOpenMenu: () => void;
};

export function ChatHeader({
  paddingTop,
  height,
  menuOverlayOpen,
  headerTitleLabel,
  titleGenerating,
  chatTitle,
  showIndicator,
  unseenCount,
  hasMessages,
  onOpenDrawer,
  onOpenReminders,
  onNewChat,
  onOpenMenu,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = makeStyles(theme);

  return (
    <View
      style={[
        s.header,
        { paddingTop, height },
        menuOverlayOpen && s.headerMuted,
      ]}
      pointerEvents={menuOverlayOpen ? "none" : "box-none"}
      collapsable={false}
      renderToHardwareTextureAndroid
    >
      <Pressable
        style={({ pressed }) => [
          s.headerBtn,
          menuOverlayOpen && s.headerBtnMuted,
          pressed && !menuOverlayOpen && s.headerBtnPressed,
        ]}
        onPress={onOpenDrawer}
        hitSlop={12}
      >
        <HamburgerIcon size={22} color={theme.text} />
      </Pressable>
      {headerTitleLabel ? (
        <View style={s.headerCenter} pointerEvents="none">
          <Text
            style={[
              s.headerTitleText,
              titleGenerating && !chatTitle && s.headerTitlePending,
            ]}
            numberOfLines={1}
          >
            {headerTitleLabel}
          </Text>
        </View>
      ) : (
        <View style={s.headerSpacer} />
      )}
      <View style={s.headerRight}>
        {showIndicator ? (
          <Pressable
            style={s.headerBtn}
            onPress={() => {
              tap();
              onOpenReminders();
            }}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel={t("reminders.badge_accessibility", {
              count: unseenCount,
            })}
          >
            <View style={s.headerIconWrap}>
              <Ionicons name="notifications-outline" size={22} color={theme.text} />
              <ReminderBadge count={unseenCount} style={s.headerBadge} />
            </View>
          </Pressable>
        ) : null}
        {hasMessages ? (
          <Pressable
            style={s.headerBtn}
            onPress={onNewChat}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel={t("chat.new_chat")}
          >
            <Ionicons name="create-outline" size={22} color={theme.text} />
          </Pressable>
        ) : null}
        {hasMessages ? (
          <Pressable
            style={s.headerBtn}
            onPress={onOpenMenu}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel={t("chat.menu")}
          >
            <Ionicons name="ellipsis-vertical" size={22} color={theme.text} />
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    header: {
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      zIndex: 100,
      flexDirection: "row",
      alignItems: "flex-end",
      paddingHorizontal: 4,
      paddingBottom: 4,
      backgroundColor: theme.bg,
    },
    headerMuted: { opacity: 0.55 },
    headerBtn: {
      width: 44,
      height: 44,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 10,
      backgroundColor: theme.bg,
      zIndex: 101,
    },
    headerBtnMuted: { backgroundColor: "transparent" },
    headerBtnPressed: { backgroundColor: theme.surfaceAlt },
    headerRight: { flexDirection: "row", alignItems: "center", zIndex: 101 },
    headerCenter: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 8,
      minWidth: 0,
      backgroundColor: theme.bg,
    },
    headerTitleText: {
      fontSize: 16,
      fontWeight: "700",
      color: theme.text,
      textAlign: "center",
    },
    headerTitlePending: {
      color: theme.textTertiary,
      fontStyle: "italic",
      fontWeight: "600",
    },
    headerIconWrap: {
      width: 24,
      height: 24,
      alignItems: "center",
      justifyContent: "center",
    },
    headerBadge: { position: "absolute", top: -4, right: -8 },
    headerSpacer: { flex: 1, pointerEvents: "none" as const },
  });
}
