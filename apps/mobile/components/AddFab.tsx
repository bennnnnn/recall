import { Platform, Pressable, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { tap } from "@/lib/haptics";
import { Theme, useTheme } from "@/lib/theme";

type Props = {
  onPress: () => void;
  accessibilityLabel: string;
};

/** Bottom-right + FAB for Add learning / New list / Add reminder. */
export function AddFab({ onPress, accessibilityLabel }: Props) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const s = makeStyles(theme);

  return (
    <Pressable
      onPress={() => {
        tap();
        onPress();
      }}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      style={[s.btn, { bottom: Math.max(insets.bottom, 12) + 8, right: 16 + insets.right }]}
    >
      <Ionicons name="add" size={28} color={theme.onPrimary} />
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
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
      ...Platform.select({
        ios: {
          shadowColor: theme.primary,
          shadowOffset: { width: 0, height: 4 },
          shadowOpacity: theme.isDark ? 0.35 : 0.28,
          shadowRadius: 8,
        },
        android: { elevation: 6 },
      }),
    },
  });
}
