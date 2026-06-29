import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { C } from "@/constants/Colors";

type Props = {
  count: number;
  style?: StyleProp<ViewStyle>;
};

export function ReminderBadge({ count, style }: Props) {
  if (count <= 0) return null;
  const label = count > 99 ? "99+" : String(count);
  return (
    <View style={[s.badge, style]}>
      <Text style={s.text}>{label}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  badge: {
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 5,
    backgroundColor: "#e74c3c",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    borderColor: C.surface,
  },
  text: {
    fontSize: 11,
    fontWeight: "700",
    color: "#fff",
    lineHeight: 13,
  },
});
