import { Pressable, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  onPress: () => void;
  accessibilityLabel: string;
};

/** Compact header + control — primaryLight chip matching former “Add …” bars. */
export function HeaderAddButton({ onPress, accessibilityLabel }: Props) {
  const theme = useTheme();
  const s = makeStyles(theme);

  return (
    <Pressable
      onPress={onPress}
      hitSlop={6}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      style={s.btn}
    >
      <Ionicons name="add" size={24} color={theme.primary} />
    </Pressable>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    btn: {
      marginRight: 4,
      width: 36,
      height: 36,
      borderRadius: 18,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
