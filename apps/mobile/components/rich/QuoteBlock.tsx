import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { RichBodyText } from "@/components/rich/RichBodyText";
import { Theme, useTheme } from "@/lib/theme";

type Props = { quote: string; author?: string };

export function QuoteBlock({ quote, author }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.wrap}>
      <Ionicons
        name="chatbox-ellipses-outline"
        size={18}
        color={theme.textTertiary}
        style={s.icon}
      />
      <RichBodyText style={s.quote} selectable>
        {quote}
      </RichBodyText>
      {author ? <Text style={s.author}>— {author}</Text> : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      backgroundColor: t.contentSurface,
      borderLeftWidth: 3,
      borderLeftColor: t.primary,
      borderRadius: 10,
      paddingHorizontal: 14,
      paddingVertical: 12,
      marginVertical: 8,
    },
    icon: { marginBottom: 6 },
    quote: { fontSize: 16, lineHeight: 24, color: t.text, fontStyle: "italic" },
    author: {
      marginTop: 8,
      fontSize: 14,
      fontWeight: "600",
      color: t.textSecondary,
    },
  });
}
