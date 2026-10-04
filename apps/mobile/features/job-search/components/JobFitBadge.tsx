import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

export function JobFitBadge({ label, outdated }: { label?: string; outdated?: boolean; score?: number | null }) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  if (outdated) return null;
  const key = label === "Strong fit" ? "fit_strong" : label === "Potential fit" ? "fit_potential" : "fit_review";
  const color = label === "Strong fit" ? C.primary : C.textSecondary;
  const text = t(`my_job.${key}`);
  return (
    <View style={s.badge} accessibilityLabel={text}>
      <Text style={[s.text, { color }]}>{text}</Text>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    badge: {
      alignSelf: "flex-start",
      minHeight: 32,
      minWidth: 56,
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: Space.xs,
      borderRadius: Radius.full,
      backgroundColor: C.surfaceAlt,
    },
    text: { ...Type.secondary, ...Weight.bold },
  });
}
