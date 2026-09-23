import { useEffect, useMemo, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Image } from "expo-image";

import { type Theme, useTheme } from "@/lib/theme";

export function CompanyLogo({
  company,
  uri,
  size = 48,
}: {
  company: string;
  uri: string | null;
  size?: number;
}) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const [failed, setFailed] = useState(false);
  const initial = company.trim().charAt(0).toUpperCase() || "J";

  useEffect(() => setFailed(false), [uri]);

  return (
    <View
      style={[
        s.logo,
        { width: size, height: size, borderRadius: Math.round(size * 0.31) },
      ]}
      accessibilityLabel={company}
    >
      {uri && !failed ? (
        <Image
          testID="company-logo-image"
          source={{ uri }}
          style={{ width: size - 10, height: size - 10 }}
          contentFit="contain"
          cachePolicy="memory-disk"
          onError={() => setFailed(true)}
        />
      ) : (
        <Text style={[s.initial, { fontSize: size * 0.36 }]}>{initial}</Text>
      )}
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    logo: {
      alignItems: "center",
      justifyContent: "center",
      overflow: "hidden",
      backgroundColor: C.surfaceAlt,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
    },
    initial: { color: C.primary, fontWeight: "800" },
  });
}
