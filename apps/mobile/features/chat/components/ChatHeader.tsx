import { memo, useCallback, useMemo, useRef, type RefObject } from "react";
import { StyleSheet, Text, View, type LayoutChangeEvent, type HostInstance } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useLocalSearchParams, useRouter } from "expo-router";
import { HeaderButton, HeaderButtonGroup } from "@/ui/controls/HeaderButton";
import { useTranslation } from "react-i18next";

import {
  CHROME_FADE_EXTRA,
  TOP_CHROME_FADE_LOCATIONS,
  topChromeFadeColors,
} from "@/features/chat/components/chromeFade";
import { Theme, useTheme } from "@/lib/theme";
import { Italic, Type, Weight } from "@/lib/type";
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
  /** Attached to ⋮ so the chat menu opens from it. */
  menuAnchorRef?: RefObject<HostInstance | null>;
};

/** Opened over another page (Library's "Open chat", a memory fact's "From" line): the
 *  leading button goes back to it instead of opening the drawer. */
function opensOverAPage(returnTo: string | undefined): boolean {
  return returnTo === "gallery" || returnTo === "memory";
}

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
  menuAnchorRef,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const { returnTo } = useLocalSearchParams<{ returnTo?: string }>();
  const router = useRouter();
  const openedOver = opensOverAPage(returnTo);
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
        <HeaderButton
          icon={openedOver ? "arrow-left" : "menu"}
          variant={openedOver ? "plain" : "plate"}
          onPress={() => {
            if (openedOver) {
              if (router.canGoBack()) router.back();
              else router.replace("/");
              return;
            }
            onOpenDrawer();
          }}
          accessibilityLabel={openedOver ? t("common.back") : t("chat.open_drawer_a11y")}
          testID="chat-header-leading"
        />
        {headerTitleLabel ? (
          <View style={s.headerCenter} pointerEvents="none">
            <Text
              style={[
                s.headerTitleText,
                titleGenerating && !chatTitle && s.headerTitlePending,
              ]}
              numberOfLines={1}
              accessibilityRole="header"
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
            <HeaderButtonGroup>
              <HeaderButton
                variant="plain"
                icon="edit"
                onPress={onNewChat}
                accessibilityLabel={t("chat.new_chat")}
              />
              <HeaderButton
                ref={menuAnchorRef}
                variant="plain"
                icon="more-vertical"
                onPress={onOpenMenu}
                accessibilityLabel={t("chat.menu")}
              />
            </HeaderButtonGroup>
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
      paddingHorizontal: Space.sm,
      paddingBottom: Space.xxs,
      backgroundColor: "transparent",
    },
    headerMuted: { opacity: 0.55 },
    headerRight: { flexDirection: "row", alignItems: "center", gap: 2 },
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
      ...Italic.semibold,
    },
    headerSpacer: { flex: 1, pointerEvents: "none" as const },
  });
}
