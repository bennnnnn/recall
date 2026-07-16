import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, ViewStyle } from "react-native";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";

import { notifySuccess, tap } from "@/lib/haptics";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  text: string;
  /** "pill" = compact icon+label for code/copy/card headers; "action" = larger button for chart/mermaid rows. */
  variant?: "pill" | "action";
  /** Disable haptic feedback if a parent already fired one. */
  haptic?: boolean;
  style?: ViewStyle;
  hitSlop?: number;
  /** Override the a11y label (defaults to the visible "Copy"/"Copied" label). */
  accessibilityLabel?: string;
};

const COPIED_RESET_MS = 1500;

export function CopyButton({
  text,
  variant = "pill",
  haptic = true,
  style,
  hitSlop = 8,
  accessibilityLabel,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme, variant), [theme, variant]);
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  const onCopy = async () => {
    if (!text.trim()) return;
    if (haptic) tap();
    await Clipboard.setStringAsync(text);
    setCopied(true);
    notifySuccess();
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopied(false), COPIED_RESET_MS);
  };

  const iconSize = variant === "action" ? 18 : 14;
  const label = copied ? t("common.copied") : t("common.copy");

  return (
    <Pressable
      style={[s.btn, style]}
      onPress={onCopy}
      hitSlop={hitSlop}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={copied ? { selected: true } : undefined}
    >
      <Ionicons
        name={copied ? (variant === "action" ? "checkmark-circle" : "checkmark-outline") : "copy-outline"}
        size={iconSize}
        color={copied ? theme.primary : theme.textSecondary}
      />
      <Text style={[s.label, copied && s.labelDone]}>{label}</Text>
    </Pressable>
  );
}

function makeStyles(t: Theme, variant: "pill" | "action") {
  if (variant === "action") {
    return StyleSheet.create({
      btn: {
        flexDirection: "row",
        alignItems: "center",
        gap: 6,
        paddingVertical: 8,
        paddingHorizontal: 14,
        borderRadius: 10,
        backgroundColor: t.surface,
        borderWidth: StyleSheet.hairlineWidth,
        borderColor: t.border,
      },
      label: { fontSize: 14, fontWeight: "600", color: t.textSecondary },
      labelDone: { color: t.primary },
    });
  }
  return StyleSheet.create({
    btn: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      paddingHorizontal: 8,
      paddingVertical: 4,
      borderRadius: 8,
      backgroundColor: t.bg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
    },
    label: { fontSize: 12, fontWeight: "600", color: t.textSecondary },
    labelDone: { color: t.primary },
  });
}
