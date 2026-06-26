import { StyleSheet, Text, View } from "react-native";

import { CardShell } from "@/components/rich/CardShell";
import { C } from "@/constants/Colors";

type Props = { text: string; label?: string };

export function MessagePreview({ text, label = "Message draft" }: Props) {
  return (
    <CardShell
      label={label}
      copyText={text}
      icon="chatbubble-outline"
      accentColor="#34C759"
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

const s = StyleSheet.create({
  previewArea: { alignItems: "flex-end", gap: 4 },
  bubble: {
    maxWidth: "92%",
    backgroundColor: "#007AFF",
    borderRadius: 18,
    borderBottomRightRadius: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  bubbleText: { color: "#fff", fontSize: 16, lineHeight: 22 },
  hint: { fontSize: 11, color: C.textTertiary, marginRight: 4 },
});
