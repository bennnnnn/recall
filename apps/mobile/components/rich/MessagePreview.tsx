import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { CardShell } from "@/components/rich/CardShell";
import { Theme, useTheme } from "@/lib/theme";

type Props = { text: string; label?: string };

export function MessagePreview({ text, label = "Message draft" }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <CardShell
      label={label}
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
        <Text style={s.hint}>Preview</Text>
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
