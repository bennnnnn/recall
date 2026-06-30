import { useMemo } from "react";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  count: number;
  style?: StyleProp<ViewStyle>;
};

export function ReminderBadge({ count, style }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  if (count <= 0) return null;
  const label = count > 99 ? "99+" : String(count);
  return (
    <View style={[s.badge, style]}>
      <Text style={s.text}>{label}</Text>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    badge: {
      minWidth: 18,
      height: 18,
      borderRadius: 9,
      paddingHorizontal: 5,
      backgroundColor: theme.danger,
      alignItems: "center",
      justifyContent: "center",
      borderWidth: 1.5,
      borderColor: theme.surface,
    },
    text: {
      fontSize: 11,
      fontWeight: "700",
      color: theme.onPrimary,
      lineHeight: 13,
    },
  });
}
