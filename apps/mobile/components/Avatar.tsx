import { useMemo } from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import { getInitials } from "@/lib/profile";
import { Theme, useTheme } from "@/lib/theme";

/** Google profile picture when available, otherwise the user's initials. */
export function Avatar({
  name,
  uri,
  size = 34,
}: {
  name: string | null;
  uri?: string | null;
  size?: number;
}) {
  const theme = useTheme();
  const styles = useMemo(() => makeStyles(theme), [theme]);
  const dim = { width: size, height: size, borderRadius: size / 2 };

  if (uri) {
    return (
      <Image source={{ uri }} style={[dim, { backgroundColor: theme.surface }]} />
    );
  }
  return (
    <View style={[dim, styles.fallback]}>
      <Text style={[styles.text, { fontSize: size * 0.4 }]}>{getInitials(name)}</Text>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    fallback: {
      backgroundColor: theme.primary,
      alignItems: "center",
      justifyContent: "center",
    },
    text: { color: "#fff", fontWeight: "700" },
  });
}
