/**
 * In place of a card a newer Recall draws (lib/fence/newerCard.ts): a quiet line asking
 * for the update, never the card's raw JSON.
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { StyleSheet, Text, View } from "react-native";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

export function NewerCardNote() {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={s.box} testID="newer-card-note" accessible>
      <Icon name="info" size={IconSize.sm} color={theme.textSecondary} />
      <Text style={s.text}>{t("rich.newer_card")}</Text>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    box: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xs,
      paddingVertical: Space.sm,
      paddingHorizontal: Space.md,
      marginVertical: Space.xs,
      borderRadius: Radius.md,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: theme.border,
      backgroundColor: theme.surface,
    },
    text: { ...Type.compact, color: theme.textSecondary, flexShrink: 1 },
  });
}
