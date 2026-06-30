import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { Theme, useTheme } from "@/lib/theme";
import { formatScrollAwayBadge } from "@/lib/chatScrollLogic";

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
        <Ionicons name="chevron-down" size={22} color={C.text} />
        {badgeLabel ? (
          <View style={s.badge}>
            <Text style={s.badgeText}>{badgeLabel}</Text>
          </View>
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
      backgroundColor: C.bg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      alignItems: "center",
      justifyContent: "center",
      boxShadow: "0 2 10 0 rgba(0, 0, 0, 0.18)",
      elevation: 8,
    },
    badge: {
      position: "absolute",
      top: -4,
      right: -4,
      minWidth: 18,
      height: 18,
      borderRadius: 9,
      paddingHorizontal: 4,
      backgroundColor: C.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    badgeText: {
      fontSize: 11,
      fontWeight: "700",
      color: "#fff",
    },
  });
