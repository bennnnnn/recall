import { useMemo, type ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";

import { RichBodyText } from "@/components/rich/RichBodyText";
import { Theme, useTheme } from "@/lib/theme";

type Props = { quote?: string; author?: string; children?: ReactNode };

export function QuoteBlock({ quote, author, children }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.wrap}>
      <Icon
        name="chatbox-ellipses-outline"
        size={18}
        color={theme.textTertiary}
        style={s.icon}
      />
      {children ? (
        <View>{children}</View>
      ) : (
        <RichBodyText style={s.quote} selectable>
          {quote}
        </RichBodyText>
      )}
      {author ? <Text style={s.author}>— {author}</Text> : null}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      backgroundColor: t.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      borderRadius: 20,
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
