import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { CopyButton } from "@/components/CopyButton";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  text: string;
  label?: string;
};

export function CopyBlock({ text, label }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.wrap}>
      <View style={[s.header, !label && s.headerCompact]}>
        {label ? <Text style={s.label}>{label}</Text> : null}
        <CopyButton text={text} />
      </View>
      <Text style={s.body} selectable>
        {text}
      </Text>
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      width: "100%",
      maxWidth: "100%",
      backgroundColor: t.contentSurface,
      borderRadius: 12,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: t.border,
      marginVertical: 8,
      overflow: "hidden",
    },
    header: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8,
      paddingHorizontal: 14,
      paddingVertical: 10,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: t.border,
      backgroundColor: t.contentSurface,
    },
    headerCompact: {
      justifyContent: "flex-end",
      paddingVertical: 8,
    },
    label: {
      flex: 1,
      flexShrink: 1,
      fontSize: 13,
      fontWeight: "600",
      color: t.textSecondary,
    },
    body: {
      flexShrink: 1,
      fontSize: 16,
      lineHeight: 24,
      color: t.text,
      paddingHorizontal: 14,
      paddingVertical: 12,
      backgroundColor: t.contentSurface,
    },
  });
}
