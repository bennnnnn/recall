import { Pressable, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Theme, useTheme } from "@/lib/theme";

type Props = {
  onPress: () => void;
  accessibilityLabel: string;
};

/** Bottom-right + FAB for Add learning / New list. */
export function AddFab({ onPress, accessibilityLabel }: Props) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = makeStyles(theme);

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      style={[s.btn, { bottom: Math.max(insets.bottom, 12) + 8, right: 16 + insets.right }]}
    >
      <Ionicons name="add" size={28} color={theme.primary} />
    </Pressable>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    btn: {
      position: "absolute",
      zIndex: 20,
      width: 56,
      height: 56,
      borderRadius: 28,
      backgroundColor: theme.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
  });
}
