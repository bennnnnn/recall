/**
 * A preview card whose page the system ended twice (`useWebViewRecovery`): it says so and
 * offers Retry in the card's place, instead of a blank box.
 */
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { Theme, useTheme } from "@/lib/theme";
import { Space } from "@/lib/space";
import { Type } from "@/lib/type";
import { Button } from "@/ui/controls/Button";
import { Icon } from "@/ui/icons/Icon";
import { IconSize } from "@/ui/icons/sizes";

export function PreviewLostNote({ onRetry, style }: { onRetry: () => void; style?: StyleProp<ViewStyle> }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  return (
    <View style={[s.box, style]} testID="preview-lost">
      <Icon name="alert-circle" size={IconSize.sm} color={theme.textSecondary} />
      <Text style={s.text}>{t("preview.lost")}</Text>
      <Button title={t("common.retry")} onPress={onRetry} variant="secondary" size="sm" testID="preview-lost-retry" />
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    box: {
      alignItems: "center",
      justifyContent: "center",
      gap: Space.xs,
      paddingVertical: Space.lg,
      paddingHorizontal: Space.md,
    },
    text: { ...Type.compact, color: theme.textSecondary, textAlign: "center" },
  });
}
