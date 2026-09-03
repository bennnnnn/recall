import { useMemo } from "react";
import { Pressable, StyleSheet, Text } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

type Props = {
  onRetry: () => void;
  /** Hide the word "Retry" on tiny thumbs; a11y label still reads it. */
  compact?: boolean;
};

export function MediaLoadRetry({ onRetry, compact = false }: Props) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);

  return (
    <Pressable
      onPress={onRetry}
      accessibilityRole="button"
      accessibilityLabel={t("common.retry")}
      testID="media-load-retry"
      hitSlop={compact ? 4 : 8}
      style={s.btn}
    >
      <Icon
        name="refresh-outline"
        size={compact ? 20 : 28}
        color={C.textSecondary}
      />
      {compact ? null : <Text style={s.label}>{t("common.retry")}</Text>}
    </Pressable>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    btn: {
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xxs,
      paddingHorizontal: Space.xs,
      paddingVertical: Space.xxs,
    },
    label: {
      ...Type.caption,
      color: C.textSecondary,
    },
  });
}
