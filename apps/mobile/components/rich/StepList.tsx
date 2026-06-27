import { StyleSheet, Text, View } from "react-native";

import { C } from "@/constants/Colors";

type Props = { steps: string[] };

export function StepList({ steps }: Props) {
  return (
    <View style={s.wrap}>
      {steps.map((step, index) => (
        <View key={`step-${index}`} style={[s.row, index > 0 && s.rowGap]}>
          <View style={s.badge}>
            <Text style={s.badgeText}>{index + 1}</Text>
          </View>
          <Text style={s.text} selectable>
            {step}
          </Text>
        </View>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { marginVertical: 8, gap: 0 },
  row: {
    flexDirection: "row",
    gap: 12,
    alignItems: "flex-start",
    backgroundColor: C.bg,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  rowGap: { marginTop: 8 },
  badge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: C.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: { fontSize: 14, fontWeight: "700", color: C.primary },
  text: { flex: 1, fontSize: 16, lineHeight: 24, color: C.text, paddingTop: 2 },
});
