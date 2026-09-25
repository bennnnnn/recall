import { useEffect, useMemo, useRef, useState } from "react";
import { StyleSheet, ViewStyle } from "react-native";
import * as Clipboard from "expo-clipboard";
import { useTranslation } from "react-i18next";

import { IconButton } from "@/components/IconButton";
import { notifySuccess } from "@/lib/haptics";
import { inkIconColor } from "@/lib/icons";
import { useTheme } from "@/lib/theme";

type Props = {
  text: string;
  /** Disable haptic feedback if a parent already fired one. */
  haptic?: boolean;
  style?: ViewStyle;
  /** Override the a11y label (defaults to "Copy" / "Copied"). */
  accessibilityLabel?: string;
};

const COPIED_RESET_MS = 1500;
const ICON_SIZE = 20;

export function CopyButton({
  text,
  haptic = true,
  style,
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
    await Clipboard.setStringAsync(text);
    setCopied(true);
    if (haptic) notifySuccess();
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopied(false), COPIED_RESET_MS);
  };

  const label = copied ? t("common.copied") : t("common.copy");
  const ink = copied ? theme.primary : inkIconColor(theme);

  return (
    <IconButton
      name={copied ? "checkmark-outline" : "copy-outline"}
      size={ICON_SIZE}
      color={ink}
      onPress={() => void onCopy()}
      accessibilityLabel={accessibilityLabel ?? label}
      style={[s.btn, style]}
    />
  );
}

function makeStyles() {
  return StyleSheet.create({
    btn: {
      // 44×44 touch target; negative margins keep the visual footprint at the
      // old 32×32 so card headers don't grow.
      width: 44,
      height: 44,
      margin: -6,
    },
  });
}
