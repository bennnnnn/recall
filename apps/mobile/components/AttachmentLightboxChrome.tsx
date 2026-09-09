import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import type { EdgeInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { useTheme } from "@/lib/theme";
import { IconSize } from "@/lib/icons";

const LIGHTBOX_FG = "#FFFFFF";
const ICON_CHIP_BG = "rgba(255, 255, 255, 0.18)";
const MENU_BG = "rgba(28, 28, 30, 0.94)";

export { LIGHTBOX_FG, ICON_CHIP_BG };

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
          <Icon name="close" size={IconSize.md} color={LIGHTBOX_FG} />
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
              <ActivityIndicator color={LIGHTBOX_FG} size="small" />
            ) : (
              <Icon name="share-outline" size={IconSize.md} color={LIGHTBOX_FG} />
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
              <ActivityIndicator color={LIGHTBOX_FG} size="small" />
            ) : (
              <Icon name="download-outline" size={IconSize.md} color={LIGHTBOX_FG} />
            )}
          </Pressable>
          {showOverflow ? (
            <Pressable
              style={s.iconBtn}
              onPress={onToggleOverflow}
              hitSlop={8}
              accessibilityLabel={t("preview.more_a11y")}
            >
              <Icon name="ellipsis-horizontal-outline" size={IconSize.md} color={LIGHTBOX_FG} />
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
                <Icon name="attach-outline" size={IconSize.sm} color={LIGHTBOX_FG} />
                <Text style={s.menuLabel}>{t("gallery.use_in_chat")}</Text>
              </Pressable>
            ) : null}
            {showOpenChat ? (
              <Pressable
                style={({ pressed }) => [s.menuRow, pressed && s.menuRowPressed]}
                onPress={onOpenChat}
                accessibilityLabel={t("gallery.open_chat_a11y")}
              >
                <Icon name="chatbubble-outline" size={IconSize.sm} color={LIGHTBOX_FG} />
                <Text style={s.menuLabel}>{t("gallery.open_chat")}</Text>
              </Pressable>
            ) : null}
            {showDelete ? (
              <Pressable
                style={({ pressed }) => [s.menuRow, pressed && s.menuRowPressed]}
                onPress={onDelete}
                accessibilityLabel={t("common.delete")}
              >
                <Icon name="trash-outline" size={IconSize.sm} danger />
                <Text style={[s.menuLabel, { color: theme.danger }]}>{t("common.delete")}</Text>
              </Pressable>
            ) : null}
          </View>
        </>
      ) : null}
    </>
  );
}

const s = StyleSheet.create({
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
    backgroundColor: ICON_CHIP_BG,
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
    backgroundColor: "rgba(255,255,255,0.35)",
  },
  dotActive: {
    backgroundColor: LIGHTBOX_FG,
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
    borderRadius: 14,
    backgroundColor: MENU_BG,
    overflow: "hidden",
  },
  menuRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    paddingHorizontal: 18,
    paddingVertical: 16,
  },
  menuRowPressed: {
    backgroundColor: "rgba(255,255,255,0.08)",
  },
  menuLabel: {
    flex: 1,
    fontSize: 17,
    color: LIGHTBOX_FG,
  },
});
