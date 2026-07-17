import { memo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { HamburgerIcon } from "@/components/HamburgerIcon";
import { ReminderBadge } from "@/components/ReminderBadge";
import {
  CHROME_FADE_EXTRA,
  TOP_CHROME_FADE_LOCATIONS,
  topChromeFadeColors,
} from "@/lib/chromeFade";
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
  /** False on the empty home screen (no turns yet). Hides new-chat + ⋮. */
  hasMessages: boolean;
  onOpenDrawer: () => void;
  onOpenReminders: () => void;
  onNewChat: () => void;
  onOpenMenu: () => void;
};

export const ChatHeader = memo(function ChatHeader({
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
      style={s.headerWrap}
      pointerEvents={menuOverlayOpen ? "none" : "box-none"}
      collapsable={false}
    >
      <LinearGradient
        colors={topChromeFadeColors(theme) as [string, string, ...string[]]}
        locations={[...TOP_CHROME_FADE_LOCATIONS]}
        style={[s.headerFade, { height: height + CHROME_FADE_EXTRA }]}
        pointerEvents="none"
      />
      <View
        style={[
          s.header,
          { paddingTop, height },
          menuOverlayOpen && s.headerMuted,
        ]}
        pointerEvents="box-none"
      >
        <Pressable
          style={({ pressed }) => [
            s.headerBtn,
            menuOverlayOpen && s.headerBtnMuted,
            pressed && !menuOverlayOpen && s.headerBtnPressed,
          ]}
          onPress={onOpenDrawer}
          hitSlop={12}
          accessibilityRole="button"
          accessibilityLabel={t("chat.open_drawer_a11y")}
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
          {/* Home (no turns): drawer only. New-chat + ⋮ only once there are messages. */}
          {hasMessages ? (
            <View style={s.actionGroup}>
              <Pressable
                style={({ pressed }) => [
                  s.actionGroupBtn,
                  pressed && s.actionGroupBtnPressed,
                ]}
                onPress={onNewChat}
                hitSlop={4}
                accessibilityRole="button"
                accessibilityLabel={t("chat.new_chat")}
              >
                <Ionicons name="chatbubble-outline" size={22} color={theme.text} />
              </Pressable>
              <Pressable
                style={({ pressed }) => [
                  s.actionGroupBtn,
                  pressed && s.actionGroupBtnPressed,
                ]}
                onPress={onOpenMenu}
                hitSlop={4}
                accessibilityRole="button"
                accessibilityLabel={t("chat.menu")}
              >
                <Ionicons name="ellipsis-vertical" size={22} color={theme.text} />
              </Pressable>
            </View>
          ) : null}
        </View>
      </View>
    </View>
  );
});

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    headerWrap: {
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      zIndex: 100,
      overflow: "visible",
    },
    headerFade: {
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
    },
    header: {
      flexDirection: "row",
      alignItems: "flex-end",
      paddingHorizontal: 4,
      paddingBottom: 4,
      backgroundColor: "transparent",
    },
    headerMuted: { opacity: 0.55 },
    headerBtn: {
      width: 44,
      height: 44,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 10,
      backgroundColor: theme.bg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
    },
    headerBtnMuted: { backgroundColor: theme.bg },
    headerBtnPressed: { backgroundColor: theme.surfaceAlt },
    headerRight: { flexDirection: "row", alignItems: "center", gap: 2 },
    actionGroup: {
      flexDirection: "row",
      alignItems: "center",
      height: 44,
      borderRadius: 10,
      backgroundColor: theme.bg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      overflow: "hidden",
      paddingHorizontal: 2,
    },
    actionGroupBtn: {
      width: 36,
      height: 40,
      alignItems: "center",
      justifyContent: "center",
    },
    actionGroupBtnPressed: { backgroundColor: theme.surfaceAlt },
    headerCenter: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 8,
      minWidth: 0,
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
