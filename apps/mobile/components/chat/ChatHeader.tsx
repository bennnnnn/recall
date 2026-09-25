import { memo, useCallback, useMemo, useRef } from "react";
import { StyleSheet, Text, View, type LayoutChangeEvent } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Icon } from "@/ui/icons/Icon";
import { IconButton } from "@/ui/controls/IconButton";
import { useTranslation } from "react-i18next";

import {
  CHROME_FADE_EXTRA,
  TOP_CHROME_FADE_LOCATIONS,
  topChromeFadeColors,
} from "@/lib/chromeFade";
import { Theme, useTheme } from "@/lib/theme";
import { EditIcon, IconSize, MenuIcon } from "@/lib/icons";
import { Type, Weight } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

type Props = {
  paddingTop: number;
  minimumHeight: number;
  onHeightChange: (height: number) => void;
  menuOverlayOpen: boolean;
  headerTitleLabel: string | null;
  titleGenerating: boolean;
  chatTitle: string | null;
  /** False on the empty home screen (no turns yet). Hides new-chat + ⋮. */
  hasMessages: boolean;
  onOpenDrawer: () => void;
  onNewChat: () => void;
  onOpenMenu: () => void;
};

export const ChatHeader = memo(function ChatHeader({
  paddingTop,
  minimumHeight,
  onHeightChange,
  menuOverlayOpen,
  headerTitleLabel,
  titleGenerating,
  chatTitle,
  hasMessages,
  onOpenDrawer,
  onNewChat,
  onOpenMenu,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const router = useRouter();
  const fromLibrary = returnTo === "gallery";
  const lastReportedHeight = useRef(0);
  const handleLayout = useCallback(
    (event: LayoutChangeEvent) => {
      const next = Math.ceil(event.nativeEvent.layout.height);
      if (next <= 0 || next === lastReportedHeight.current) return;
      lastReportedHeight.current = next;
      onHeightChange(next);
    },
    [onHeightChange],
  );

  return (
    <View
      style={s.headerWrap}
      pointerEvents={menuOverlayOpen ? "none" : "box-none"}
      collapsable={false}
    >
      <LinearGradient
        colors={topChromeFadeColors(theme) as [string, string, ...string[]]}
        locations={[...TOP_CHROME_FADE_LOCATIONS]}
        style={s.headerFade}
        pointerEvents="none"
      />
      <View
        style={[
          s.header,
          { paddingTop, minHeight: minimumHeight },
          menuOverlayOpen && s.headerMuted,
        ]}
        onLayout={handleLayout}
        testID="chat-header"
        pointerEvents="box-none"
      >
        <View style={s.headerBtnPlate}>
          <IconButton
            style={s.headerBtn}
            pressedStyle={menuOverlayOpen ? undefined : s.headerBtnPressed}
            onPress={() => {
              if (fromLibrary) {
                if (router.canGoBack()) router.back();
                else router.replace("/");
                return;
              }
              onOpenDrawer();
            }}
            accessibilityLabel={fromLibrary ? t("common.back") : t("chat.open_drawer_a11y")}
            icon={
              fromLibrary ? (
                <Icon name="chevron-back" size={IconSize.md} color={theme.text} />
              ) : (
                <MenuIcon size={IconSize.md} color={theme.text} />
              )
            }
          />
        </View>
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
          {/* Home (no turns): drawer only. New-chat + ⋮ only once there are messages. */}
          {hasMessages ? (
            <View style={s.actionGroup}>
              <IconButton
                style={s.actionGroupBtn}
                pressedStyle={s.actionGroupBtnPressed}
                onPress={onNewChat}
                accessibilityLabel={t("chat.new_chat")}
                icon={<EditIcon size={IconSize.md} color={theme.text} />}
              />
              <IconButton
                style={s.actionGroupBtn}
                pressedStyle={s.actionGroupBtnPressed}
                onPress={onOpenMenu}
                accessibilityLabel={t("chat.menu")}
                name="ellipsis-vertical"
                size={IconSize.md}
                color={theme.text}
              />
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
      bottom: -CHROME_FADE_EXTRA,
    },
    header: {
      flexDirection: "row",
      alignItems: "flex-end",
      paddingHorizontal: Space.xxs,
      paddingBottom: Space.xxs,
      backgroundColor: "transparent",
    },
    headerMuted: { opacity: 0.55 },
    headerBtnPlate: {
      backgroundColor: theme.inputBg,
      borderRadius: Radius.sm,
    },
    headerBtn: {
      width: 44,
      height: 44,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: Radius.sm,
    },
    headerBtnPressed: { backgroundColor: theme.surfaceAlt },
    headerRight: { flexDirection: "row", alignItems: "center", gap: 2 },
    actionGroup: {
      flexDirection: "row",
      alignItems: "center",
      height: 44,
      overflow: "hidden",
      backgroundColor: theme.inputBg,
      borderRadius: Radius.sm,
    },
    actionGroupBtn: {
      width: 44,
      height: 44,
      alignItems: "center",
      justifyContent: "center",
    },
    actionGroupBtnPressed: { backgroundColor: theme.surfaceAlt },
    headerCenter: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: Space.xs,
      minWidth: 0,
    },
    headerTitleText: {
      ...Type.navTitle,
      ...Weight.bold,
      color: theme.text,
      textAlign: "center",
    },
    headerTitlePending: {
      color: theme.textTertiary,
      fontStyle: "italic",
      ...Weight.semibold,
    },
    headerSpacer: { flex: 1, pointerEvents: "none" as const },
  });
}
