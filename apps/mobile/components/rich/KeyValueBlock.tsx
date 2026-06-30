import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { Theme, useTheme } from "@/lib/theme";

type Props = { rows: { key: string; value: string }[] };

export function KeyValueBlock({ rows }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.wrap}>
      {rows.map((row, i) => (
        <View key={`${row.key}-${i}`} style={[s.row, i > 0 && s.rowBorder]}>
          <Text style={s.key}>{row.key}</Text>
          <Text style={s.value} selectable>
            {row.value || "—"}
          </Text>
        </View>
      ))}
    </View>
  );
}

function makeStyles(t: Theme) {
  return StyleSheet.create({
    wrap: {
      alignSelf: "stretch",
      borderRadius: 12,
      borderWidth: 1,
      borderColor: t.border,
      backgroundColor: t.bg,
      marginVertical: 8,
      overflow: "hidden",
    },
    row: {
      flexDirection: "row",
      gap: 12,
      paddingHorizontal: 12,
      paddingVertical: 10,
      alignItems: "flex-start",
    },
    rowBorder: {
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
    },
    key: {
      width: "38%",
      fontSize: 14,
      fontWeight: "600",
      color: t.textSecondary,
      lineHeight: 20,
    },
    value: { flex: 1, fontSize: 15, lineHeight: 21, color: t.text },
  });
}
