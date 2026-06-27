import { StyleSheet, Text, View } from "react-native";

import { ComparisonDraft } from "@/lib/richBlocks";
import { C } from "@/constants/Colors";

type Props = { data: ComparisonDraft };

export function ComparisonBlock({ data }: Props) {
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

const s = StyleSheet.create({
  wrap: {
    alignSelf: "stretch",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.bg,
    marginVertical: 8,
    overflow: "hidden",
  },
  row: { flexDirection: "row" },
  col: { flex: 1, padding: 12, gap: 6 },
  leftCol: { backgroundColor: "#F0FFF4" },
  rightCol: { backgroundColor: "#FFF5F5" },
  divider: { width: StyleSheet.hairlineWidth, backgroundColor: C.border },
  heading: { fontSize: 14, fontWeight: "700", color: C.text, marginBottom: 4 },
  itemRow: { flexDirection: "row", gap: 6, alignItems: "flex-start" },
  bullet: { fontSize: 14, fontWeight: "700", color: "#34C759", lineHeight: 21 },
  bulletNeg: { color: "#FF3B30" },
  item: { flex: 1, fontSize: 15, lineHeight: 21, color: C.text },
});
