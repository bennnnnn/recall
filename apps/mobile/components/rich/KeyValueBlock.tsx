import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";

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
      borderRadius: Radius.md,
      borderWidth: 1,
      borderColor: t.border,
      backgroundColor: t.bg,
      marginVertical: Space.xs,
      overflow: "hidden",
    },
    row: {
      flexDirection: "row",
      gap: Space.sm,
      paddingHorizontal: Space.sm,
      paddingVertical: 10,
      alignItems: "flex-start",
    },
    rowBorder: {
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: t.border,
    },
    key: {
      width: "38%",
      ...Type.label,
      color: t.textSecondary,
      lineHeight: 20,
    },
    value: { flex: 1, ...Type.callout, ...Weight.regular, lineHeight: 21, color: t.text },
  });
}
