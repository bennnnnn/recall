import { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { learningProgressColors } from "@/lib/homeLearningCard";
import { Theme, useTheme } from "@/lib/theme";

export type LearningContinueProgress = {
  completedToday: number;
  dailyGoal: number;
};

type Props = {
  label: string;
  onPress: () => void;
  /** Outlined secondary style (e.g. Complete / bonus). */
  variant?: "filled" | "outline";
  /** Flush footer inside a card (no outer radius). */
  embedded?: boolean;
  /** When set, background/accent follow the same end-of-day urgency as the home card. */
  progress?: LearningContinueProgress;
};

/** "Continue · 4 left" → "4 left" | Continue ›. Other labels: centered lead ›. */
export function splitContinueCtaLabel(label: string): { prefix: string | null; lead: string } {
  const sep = " · ";
  const idx = label.indexOf(sep);
  if (idx <= 0) return { prefix: null, lead: label };
  return {
    lead: label.slice(0, idx),
    prefix: label.slice(idx + sep.length).trim(),
  };
}

export function LearningContinueCta({
  label,
  onPress,
  variant = "filled",
  embedded = false,
  progress,
}: Props) {
  const theme = useTheme();
  const s = useMemo(() => makeStyles(theme), [theme]);
  const parts = splitContinueCtaLabel(label);
  const outline = variant === "outline";
  const tint = useMemo(() => {
    if (!progress || progress.dailyGoal <= 0) return null;
    return learningProgressColors({
      completedToday: progress.completedToday,
      dailyGoal: progress.dailyGoal,
      surface: theme.surface,
      primaryLight: theme.primaryLight,
      dangerLight: theme.dangerLight,
      primary: theme.primary,
      danger: theme.danger,
    });
  }, [progress, theme]);

  const backgroundColor = outline
    ? theme.surface
    : (tint?.background ?? theme.primaryLight);
  const accent = tint?.accent ?? theme.primary;
  const borderColor = outline ? accent : undefined;

  return (
    <Pressable
      style={[
        s.cta,
        { backgroundColor },
        outline && s.ctaOutline,
        outline && borderColor ? { borderColor } : null,
        embedded && s.ctaEmbedded,
        !parts.prefix && s.ctaCentered,
      ]}
      onPress={onPress}
    >
      {parts.prefix ? (
        <Text style={[s.ctaPrefix, { color: accent }, outline && s.ctaPrefixOutline]}>
          {parts.prefix}
        </Text>
      ) : null}
      <View style={s.ctaAction}>
        <Text style={[s.ctaText, { color: accent }, outline && s.ctaTextOutline]}>
          {parts.lead}
        </Text>
        <Ionicons name="chevron-forward" size={15} color={accent} />
      </View>
    </Pressable>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    cta: {
      borderRadius: 14,
      backgroundColor: theme.primaryLight,
      paddingVertical: 14,
      paddingHorizontal: 16,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 12,
    },
    ctaOutline: {
      backgroundColor: theme.surface,
      borderWidth: 1.5,
      borderColor: theme.primary,
    },
    ctaEmbedded: {
      borderRadius: 0,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
    },
    ctaCentered: {
      justifyContent: "center",
    },
    ctaPrefix: {
      flex: 1,
      fontSize: 14,
      fontWeight: "600",
      color: theme.primary,
      opacity: 0.7,
    },
    ctaPrefixOutline: {
      opacity: 0.85,
    },
    ctaAction: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
    },
    ctaText: {
      fontSize: 15,
      fontWeight: "700",
      color: theme.primary,
    },
    ctaTextOutline: {
      fontWeight: "600",
      fontSize: 16,
    },
  });
}
