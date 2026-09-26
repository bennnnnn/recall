import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { matchScoreColor } from "@/features/job-search/components/JobMatchMetaChips";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";

export function JobFitBadge({ score }: { score: number | null }) {
  const C = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(C), [C]);
  if (score == null) return null;
  const color = matchScoreColor(score, C);
  return (
    <View style={s.badge} accessibilityLabel={t("my_job.match_fit", { score })}>
      <Text style={[s.text, { color }]}>{score}%</Text>
    </View>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    badge: {
      minHeight: 36,
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
