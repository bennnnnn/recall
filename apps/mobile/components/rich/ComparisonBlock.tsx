import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ComparisonDraft } from "@/lib/richBlocks";
import { Theme, useTheme } from "@/lib/theme";

type Props = { data: ComparisonDraft };

export function ComparisonBlock({ data }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View style={s.wrap}>
      <View style={s.row}>
        <View style={[s.col, s.leftCol]}>
          <Text style={s.heading}>{data.leftTitle}</Text>
          {data.left.map((item, i) => (
            <View key={`l-${i}`} style={s.itemRow}>
              <Text style={s.bullet}>+</Text>
              <Text style={s.item} selectable>
                {item}
              </Text>
            </View>
          ))}
        </View>
        <View style={s.divider} />
        <View style={[s.col, s.rightCol]}>
          <Text style={s.heading}>{data.rightTitle}</Text>
          {data.right.map((item, i) => (
            <View key={`r-${i}`} style={s.itemRow}>
              <Text style={[s.bullet, s.bulletNeg]}>−</Text>
              <Text style={s.item} selectable>
                {item}
              </Text>
            </View>
          ))}
        </View>
      </View>
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
    row: { flexDirection: "row" },
    col: { flex: 1, padding: 12, gap: 6 },
    leftCol: { backgroundColor: t.successLight },
    rightCol: { backgroundColor: t.dangerLight },
    divider: { width: StyleSheet.hairlineWidth, backgroundColor: t.border },
    heading: { fontSize: 14, fontWeight: "700", color: t.text, marginBottom: 4 },
    itemRow: { flexDirection: "row", gap: 6, alignItems: "flex-start" },
    bullet: { fontSize: 14, fontWeight: "700", color: t.success, lineHeight: 21 },
    bulletNeg: { color: t.danger },
    item: { flex: 1, fontSize: 15, lineHeight: 21, color: t.text },
  });
}
