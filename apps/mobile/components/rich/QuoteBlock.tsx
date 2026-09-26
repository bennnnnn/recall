import { useMemo, type ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Icon } from "@/ui/icons/Icon";

import { RichBodyText } from "@/components/rich/RichBodyText";
import { Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { IconSize } from "@/ui/icons/sizes";

type Props = { quote?: string; author?: string; children?: ReactNode };

export function QuoteBlock({ quote, author, children }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.wrap}>
      <Icon
        name="message-quote"
        size={IconSize.sm}
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
      borderRadius: Radius.card,
      paddingHorizontal: 14,
      paddingVertical: Space.sm,
      marginTop: 0,
      marginBottom: 10,
    },
    icon: { marginBottom: 6 },
    quote: { ...Type.body, lineHeight: 24, color: t.text, fontStyle: "italic" },
    author: {
      marginTop: Space.xs,
      ...Type.label,
      color: t.textSecondary,
    },
  });
}
