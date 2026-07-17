import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { CardShell } from "@/components/rich/CardShell";
import { Theme, useTheme } from "@/lib/theme";

type Props = { text: string; label?: string };

export function MessagePreview({ text, label }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const resolvedLabel = label ?? t("rich.message_draft");

  return (
    <CardShell
      label={resolvedLabel}
      copyText={text}
      icon="chatbubble-outline"
      accentColor={theme.primary}
    >
      <View style={s.previewArea}>
        <View style={s.bubble}>
          <Text style={s.bubbleText} selectable>
            {text}
          </Text>
        </View>
        <Text style={s.hint}>{t("rich.preview")}</Text>
      </View>
    </CardShell>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    previewArea: { alignItems: "flex-end", gap: 4 },
    bubble: {
      maxWidth: "92%",
      backgroundColor: t.primary,
      borderRadius: 18,
      borderBottomRightRadius: 4,
      paddingHorizontal: 14,
      paddingVertical: 10,
    },
    bubbleText: { color: t.onPrimary, fontSize: 16, lineHeight: 22 },
    hint: { fontSize: 11, color: t.textTertiary, marginRight: 4 },
  });
}
