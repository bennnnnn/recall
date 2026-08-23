import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, ViewStyle } from "react-native";
import * as Clipboard from "expo-clipboard";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { CopySquaresIcon } from "@/components/rich/chatgptDraftIcons";
import { notifySuccess, tap } from "@/lib/haptics";
import { inkIconColor } from "@/lib/icons";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  text: string;
  /** "pill" = compact icon+label for code/copy/card headers; "action" = larger button for chart/mermaid rows; "icon" = ChatGPT-style icon only. */
  variant?: "pill" | "action" | "icon";
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

  const iconSize = variant === "action" ? 18 : variant === "icon" ? 20 : 14;
  const label = copied ? t("common.copied") : t("common.copy");
  const ink = copied ? theme.primary : inkIconColor(theme);

  return (
    <Pressable
      style={[s.btn, style]}
      onPress={onCopy}
      hitSlop={hitSlop}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={copied ? { selected: true } : undefined}
    >
      {variant === "icon" ? (
        copied ? (
          <Icon name="checkmark-outline" size={iconSize} color={ink} />
        ) : (
          <CopySquaresIcon size={iconSize} color={ink} />
        )
      ) : (
        <Icon
          name={copied ? (variant === "action" ? "checkmark-circle" : "checkmark-outline") : "copy-outline"}
          size={iconSize}
          color={copied ? theme.primary : theme.textSecondary}
        />
      )}
      {variant === "icon" ? null : (
        <Text style={[s.label, copied && s.labelDone]}>{label}</Text>
      )}
    </Pressable>
  );
}

function makeStyles(t: Theme, variant: "pill" | "action" | "icon") {
  if (variant === "icon") {
    return StyleSheet.create({
      btn: {
        width: 32,
        height: 32,
        alignItems: "center",
        justifyContent: "center",
      },
      label: {},
      labelDone: {},
    });
  }
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
