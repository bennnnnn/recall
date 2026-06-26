import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { C } from "@/constants/Colors";

type Props = { quote: string; author?: string };

export function QuoteBlock({ quote, author }: Props) {
  return (
    <View style={s.wrap}>
      <Ionicons
        name="chatbox-ellipses-outline"
        size={18}
        color={C.textTertiary}
        style={s.icon}
      />
      <Text style={s.quote} selectable>
        {quote}
      </Text>
      {author ? <Text style={s.author}>— {author}</Text> : null}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: {
    alignSelf: "stretch",
    backgroundColor: C.contentSurface,
    borderLeftWidth: 3,
    borderLeftColor: C.primary,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginVertical: 8,
  },
  icon: { marginBottom: 6 },
  quote: { fontSize: 16, lineHeight: 24, color: C.text, fontStyle: "italic" },
  author: {
    marginTop: 8,
    fontSize: 14,
    fontWeight: "600",
    color: C.textSecondary,
  },
});
