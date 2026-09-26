import { useMemo, useRef } from "react";
import { StyleSheet, View } from "react-native";
import type { EdgeInsets } from "react-native-safe-area-context";
import { useTranslation } from "react-i18next";

import { HeaderButton } from "@/ui/controls/HeaderButton";
import { Menu } from "@/ui/overlay/Menu";
import { Space } from "@/lib/space";
import { type Theme, useTheme, withAlpha } from "@/lib/theme";

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
  const moreRef = useRef<View>(null);
  if (!visible) return null;

  return (
    <>
      <View
        pointerEvents="box-none"
        style={[s.header, { paddingTop: Math.max(insets.top, Space.xs) }]}
      >
        <HeaderButton
          variant="media"
          icon="close"
          onPress={onClose}
          accessibilityLabel={t("preview.close")}
        />

        <View style={s.headerActions}>
          <HeaderButton
            variant="media"
            icon="share"
            onPress={onShare}
            busy={busy === "share"}
            disabled={!canShare || busy != null}
            accessibilityLabel={t("preview.share")}
          />
          <HeaderButton
            variant="media"
            icon="download"
            onPress={onDownload}
            busy={busy === "download"}
            disabled={!canShare || busy != null}
            accessibilityLabel={t("common.download")}
          />
          {showOverflow ? (
            <HeaderButton
              ref={moreRef}
              variant="media"
              icon="more-horizontal"
              onPress={onToggleOverflow}
              accessibilityLabel={t("preview.more_a11y")}
            />
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

      <Menu
        visible={overflowOpen}
        onClose={onCloseOverflow}
        anchorRef={moreRef}
        testID="lightbox-overflow-menu"
        items={[
          ...(showUseInChat
            ? [{ key: "use", icon: "attach" as const, label: t("gallery.use_in_chat"), onPress: onUseInChat }]
            : []),
          ...(showOpenChat
            ? [{ key: "open", icon: "message" as const, label: t("gallery.open_chat"), onPress: onOpenChat }]
            : []),
          ...(showDelete
            ? [{ key: "delete", icon: "trash" as const, label: t("common.delete"), destructive: true, onPress: onDelete }]
            : []),
        ]}
      />
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
  });
}
