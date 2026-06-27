import { StyleSheet, Text, View } from "react-native";

import { C } from "@/constants/Colors";

type Props = { rows: Array<{ key: string; value: string }> };

export function KeyValueBlock({ rows }: Props) {
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
  row: {
    flexDirection: "row",
    gap: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    alignItems: "flex-start",
  },
  rowBorder: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.border,
  },
  key: {
    width: "38%",
    fontSize: 14,
    fontWeight: "600",
    color: C.textSecondary,
    lineHeight: 20,
  },
  value: { flex: 1, fontSize: 15, lineHeight: 21, color: C.text },
});
