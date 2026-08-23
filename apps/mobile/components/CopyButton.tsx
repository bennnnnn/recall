import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, ViewStyle } from "react-native";
import * as Clipboard from "expo-clipboard";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { notifySuccess, tap } from "@/lib/haptics";
import { inkIconColor } from "@/lib/icons";
import { useTheme } from "@/lib/theme";

type Props = {
  text: string;
  /** Disable haptic feedback if a parent already fired one. */
  haptic?: boolean;
  style?: ViewStyle;
  hitSlop?: number;
  /** Override the a11y label (defaults to "Copy" / "Copied"). */
  accessibilityLabel?: string;
};

const COPIED_RESET_MS = 1500;
const ICON_SIZE = 20;

export function CopyButton({
  text,
  haptic = true,
  style,
  hitSlop = 8,
  accessibilityLabel,
}: Props) {
  const { t } = useTranslation();
  const theme = useTheme();
  const s = useMemo(() => makeStyles(), []);
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
      <Icon
        name={copied ? "checkmark-outline" : "copy-outline"}
        size={ICON_SIZE}
        color={ink}
      />
    </Pressable>
  );
}

function makeStyles() {
  return StyleSheet.create({
    btn: {
      width: 32,
      height: 32,
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
