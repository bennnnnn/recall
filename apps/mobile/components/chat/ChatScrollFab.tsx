import { useMemo } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Icon } from "@/components/Icon";
import { useTranslation } from "react-i18next";

import { CountBadge } from "@/components/CountBadge";
import { Theme, useTheme } from "@/lib/theme";
import { formatScrollAwayBadge } from "@/lib/chat/scrollLogic";
import { IconSize } from "@/lib/icons";

type Props = {
  visible: boolean;
  bottomOffset: number;
  scrollAwayCount: number;
  onPress: () => void;
};

export function ChatScrollFab({ visible, bottomOffset, scrollAwayCount, onPress }: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeS(C), [C]);
  const badgeLabel = formatScrollAwayBadge(scrollAwayCount);

  if (!visible) return null;

  return (
    <View
      style={[s.overlay, { bottom: bottomOffset }]}
      pointerEvents="box-none"
    >
      <Pressable
        style={s.button}
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel={t("chat.scroll_to_latest")}
      >
        <Icon name="chevron-down" size={IconSize.md} color={C.text} />
        {badgeLabel ? (
          <CountBadge count={scrollAwayCount} max={9} style={s.badge} />
        ) : null}
      </Pressable>
    </View>
  );
}

const makeS = (C: Theme) =>
  StyleSheet.create({
    overlay: {
      position: "absolute",
      left: 0,
      right: 0,
      alignItems: "center",
      zIndex: 95,
    },
    button: {
      width: 44,
      height: 44,
      borderRadius: 22,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      alignItems: "center",
      justifyContent: "center",
    },
    badge: {
      position: "absolute",
      top: -4,
      right: -4,
    },
  });
