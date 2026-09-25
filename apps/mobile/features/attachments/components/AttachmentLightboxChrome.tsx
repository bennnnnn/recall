import { useMemo } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import type { EdgeInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme, withAlpha } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

type Props = {
  visible: boolean;
  overflowOpen: boolean;
  insets: EdgeInsets;
  busy: "download" | "share" | null;
  canShare: boolean;
  showOverflow: boolean;
  showUseInChat: boolean;
  showOpenChat: boolean;
  showDelete: boolean;
  showDots: boolean;
  pageIndex: number;
  pageCount: number;
  onClose: () => void;
  onShare: () => void;
  onDownload: () => void;
  onToggleOverflow: () => void;
  onCloseOverflow: () => void;
  onUseInChat: () => void;
  onOpenChat: () => void;
  onDelete: () => void;
};

export function AttachmentLightboxChrome({
  visible,
  overflowOpen,
  insets,
  busy,
  canShare,
  showOverflow,
  showUseInChat,
  showOpenChat,
  showDelete,
  showDots,
  pageIndex,
  pageCount,
  onClose,
  onShare,
  onDownload,
  onToggleOverflow,
  onCloseOverflow,
  onUseInChat,
  onOpenChat,
  onDelete,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  if (!visible) return null;

  return (
    <>
      <View
        pointerEvents="box-none"
        style={[s.header, { paddingTop: Math.max(insets.top, Space.xs) }]}
      >
        <Pressable
          style={s.iconBtn}
          onPress={onClose}
          hitSlop={8}
          accessibilityLabel={t("preview.close")}
        >
          <Icon name="close" size={IconSize.md} color={theme.onMedia} />
        </Pressable>

        <View style={s.headerActions}>
          <Pressable
            style={[s.iconBtn, busy === "share" && s.iconBtnDisabled]}
            onPress={onShare}
            disabled={!canShare || busy != null}
            hitSlop={8}
            accessibilityLabel={t("preview.share")}
          >
            {busy === "share" ? (
              <ActivityIndicator color={theme.onMedia} size="small" />
            ) : (
              <Icon name="share" size={IconSize.md} color={theme.onMedia} />
            )}
          </Pressable>
          <Pressable
            style={[s.iconBtn, busy === "download" && s.iconBtnDisabled]}
            onPress={onDownload}
            disabled={!canShare || busy != null}
            hitSlop={8}
            accessibilityLabel={t("common.download")}
          >
            {busy === "download" ? (
              <ActivityIndicator color={theme.onMedia} size="small" />
            ) : (
              <Icon name="download" size={IconSize.md} color={theme.onMedia} />
            )}
          </Pressable>
          {showOverflow ? (
            <Pressable
              style={s.iconBtn}
              onPress={onToggleOverflow}
              hitSlop={8}
              accessibilityLabel={t("preview.more_a11y")}
            >
              <Icon name="more-horizontal" size={IconSize.md} color={theme.onMedia} />
            </Pressable>
          ) : null}
        </View>
      </View>

      {showDots ? (
        <View style={[s.dots, { paddingBottom: Math.max(insets.bottom, Space.sm) }]}>
          {Array.from({ length: pageCount }, (_, index) => (
            <View key={index} style={[s.dot, index === pageIndex && s.dotActive]} />
          ))}
        </View>
      ) : null}

      {overflowOpen ? (
        <>
          <Pressable
            testID="lightbox-overflow-dismiss"
            style={s.menuDismiss}
            onPress={onCloseOverflow}
            accessibilityLabel={t("preview.close")}
          />
          <View
            testID="lightbox-overflow-menu"
            style={[s.menu, { marginBottom: Math.max(insets.bottom, Space.sm) }]}
          >
            {showUseInChat ? (
              <Pressable
                style={({ pressed }) => [s.menuRow, pressed && s.menuRowPressed]}
                onPress={onUseInChat}
                accessibilityLabel={t("gallery.use_in_chat")}
              >
                <Icon name="attach" size={IconSize.sm} color={theme.onMedia} />
                <Text style={s.menuLabel}>{t("gallery.use_in_chat")}</Text>
              </Pressable>
            ) : null}
            {showOpenChat ? (
              <Pressable
                style={({ pressed }) => [s.menuRow, pressed && s.menuRowPressed]}
                onPress={onOpenChat}
                accessibilityLabel={t("gallery.open_chat_a11y")}
              >
                <Icon name="message" size={IconSize.sm} color={theme.onMedia} />
                <Text style={s.menuLabel}>{t("gallery.open_chat")}</Text>
              </Pressable>
            ) : null}
            {showDelete ? (
              <Pressable
                style={({ pressed }) => [s.menuRow, pressed && s.menuRowPressed]}
                onPress={onDelete}
                accessibilityLabel={t("common.delete")}
              >
                <Icon name="trash" size={IconSize.sm} danger />
                <Text style={[s.menuLabel, { color: theme.danger }]}>{t("common.delete")}</Text>
              </Pressable>
            ) : null}
          </View>
        </>
      ) : null}
    </>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    header: {
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      zIndex: 2,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: Space.sm,
      paddingBottom: Space.xs,
    },
    headerActions: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
    },
    iconBtn: {
      width: Space.minTouch,
      height: Space.minTouch,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: Radius.full,
      backgroundColor: withAlpha(theme.onMedia, 0.18),
    },
    iconBtnDisabled: {
      opacity: 0.45,
    },
    dots: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      zIndex: 2,
      flexDirection: "row",
      justifyContent: "center",
      alignItems: "center",
      gap: 6,
      paddingTop: Space.xs,
    },
    dot: {
      width: 6,
      height: 6,
      borderRadius: 3,
      backgroundColor: withAlpha(theme.onMedia, 0.35),
    },
    dotActive: {
      backgroundColor: theme.onMedia,
    },
    menuDismiss: {
      ...StyleSheet.absoluteFill,
      zIndex: 3,
    },
    menu: {
      position: "absolute",
      left: Space.md,
      right: Space.md,
      bottom: 0,
      zIndex: 4,
      borderRadius: Radius.lg,
      backgroundColor: withAlpha(theme.mediaScrim, 0.94),
      overflow: "hidden",
    },
    menuRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 14,
      paddingHorizontal: 18,
      paddingVertical: Space.md,
    },
    menuRowPressed: {
      backgroundColor: withAlpha(theme.onMedia, 0.08),
    },
    menuLabel: {
      flex: 1,
      ...Type.navTitle,
      ...Weight.regular,
      color: theme.onMedia,
    },
  });
}
