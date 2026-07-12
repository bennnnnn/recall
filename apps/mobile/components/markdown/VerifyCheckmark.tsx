import { useMemo } from "react";
import { View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { makeVerifyCheckStyles } from "@/components/markdown/markdownContentStyles";
import { useTheme } from "@/lib/theme";

export function VerifyCheckmark() {
  const theme = useTheme();
  const s = useMemo(() => makeVerifyCheckStyles(theme), [theme]);
  return (
    <View style={s.badge}>
      <Ionicons name="checkmark" size={13} color={theme.onPrimary} />
    </View>
  );
}
