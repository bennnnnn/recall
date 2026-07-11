import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import type { ResolvedChatError } from "@/lib/chatErrorMessage";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  error: ResolvedChatError | null;
  upgradeLabel?: string;
  onUpgrade?: () => void;
  onDismiss: () => void;
  bottom: number;
};

export function ChatInlineError({
  error,
  upgradeLabel,
  onUpgrade,
  onDismiss,
  bottom,
}: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);

  if (!error) return null;

  const iconName =
    error.kind === "quota"
      ? "flash-outline"
      : error.kind === "busy"
        ? "hourglass-outline"
        : error.kind === "model_unavailable"
          ? "cloud-offline-outline"
          : "alert-circle-outline";

  return (
    <View style={[s.wrap, { bottom }]}>
      <View style={s.body}>
        <Ionicons name={iconName} size={16} color={theme.warning} style={s.icon} />
        <Text style={s.text}>{error.message}</Text>
      </View>
      {error.kind === "quota" && onUpgrade && upgradeLabel ? (
        <Pressable style={s.cta} onPress={onUpgrade}>
          <Text style={s.ctaText}>{upgradeLabel}</Text>
        </Pressable>
      ) : null}
      <Pressable
        onPress={onDismiss}
        hitSlop={8}
        style={s.close}
        accessibilityRole="button"
        accessibilityLabel="Dismiss error"
      >
        <Ionicons name="close" size={16} color={theme.textTertiary} />
      </Pressable>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    wrap: {
      position: "absolute",
      left: 12,
      right: 12,
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      backgroundColor: theme.surface,
      borderRadius: 14,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.warning,
      paddingLeft: 12,
      paddingRight: 8,
      paddingVertical: 10,
      boxShadow: "0 4 16 0 rgba(0, 0, 0, 0.12)",
      elevation: 8,
      zIndex: 20,
    },
    body: { flex: 1, flexDirection: "row", alignItems: "flex-start", gap: 8 },
    icon: { marginTop: 1, flexShrink: 0 },
    text: { flex: 1, fontSize: 13, lineHeight: 18, color: theme.text },
    cta: {
      backgroundColor: theme.primary,
      borderRadius: 999,
      paddingHorizontal: 10,
      paddingVertical: 6,
      flexShrink: 0,
    },
    ctaText: { color: theme.onPrimary, fontSize: 12, fontWeight: "700" },
    close: { padding: 4, flexShrink: 0 },
  });
}
