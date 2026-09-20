import { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export type StatusPillTone = "accent" | "success" | "neutral";

type Props = {
  label: string;
  tone?: StatusPillTone;
};

/** Semantic, Dynamic-Type-safe status label. */
export function StatusPill({ label, tone = "accent" }: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);

  return (
    <View
      style={[
        s.pill,
        tone === "success" && s.success,
        tone === "neutral" && s.neutral,
      ]}
    >
      <Text
        style={[
          s.label,
          tone === "success" && s.successLabel,
          tone === "neutral" && s.neutralLabel,
        ]}
      >
        {label}
      </Text>
    </View>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    pill: {
      paddingHorizontal: Space.xs,
      paddingVertical: 2,
      borderRadius: Radius.full,
      backgroundColor: theme.primaryLight,
    },
    success: {
      backgroundColor: theme.successLight,
    },
    neutral: {
      backgroundColor: theme.surfaceAlt,
    },
    label: {
      ...Type.compact,
      color: theme.primaryDark,
      fontWeight: "700",
    },
    successLabel: {
      color: theme.text,
    },
    neutralLabel: {
      color: theme.textTertiary,
    },
  });
}
