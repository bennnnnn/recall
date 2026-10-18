import { useMemo } from "react";
import { StyleSheet, View } from "react-native";
import { useTranslation } from "react-i18next";

import { CardShell } from "@/components/rich/CardShell";
import { RichBodyText } from "@/components/rich/RichBodyText";
import { Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { Space } from "@/lib/space";
import { Radius } from "@/lib/radius";

type PhysicsSolutionPayload = {
  given: string[];
  find: string;
  formula: string[];
  assumptions: string[];
  substitution: string[];
  answer: string;
};

export function PhysicsSolutionBlock({ content }: { content: string }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const s = useMemo(() => makeStyles(theme), [theme]);

  let payload: PhysicsSolutionPayload;
  try {
    payload = JSON.parse(content);
  } catch {
    return null;
  }

  return (
    <CardShell
      label={t("rich.physics_solution") || "Physics Solution"}
      icon="lightbulb"
      accentColor={theme.primary}
      iconColor={theme.primary}
    >
      <View style={s.container}>
        {payload.given?.length > 0 && (
          <View style={s.section}>
            <RichBodyText style={s.heading}>**Given**</RichBodyText>
            <View style={s.grid}>
              {payload.given.map((g, idx) => (
                <View key={`given-${idx}`} style={s.gridItem}>
                  <RichBodyText style={s.body}>{g}</RichBodyText>
                </View>
              ))}
            </View>
          </View>
        )}

        {payload.find && (
          <View style={s.section}>
            <RichBodyText style={s.heading}>**Find**</RichBodyText>
            <RichBodyText style={s.body}>{payload.find}</RichBodyText>
          </View>
        )}

        {payload.formula?.length > 0 && (
          <View style={s.section}>
            <RichBodyText style={s.heading}>**Formula**</RichBodyText>
            {payload.formula.map((f, idx) => (
              <RichBodyText key={`formula-${idx}`} style={s.body}>
                {f}
              </RichBodyText>
            ))}
          </View>
        )}

        {payload.assumptions?.length > 0 && (
          <View style={s.section}>
            {payload.assumptions.map((a, idx) => (
              <RichBodyText key={`assumption-${idx}`} style={s.muted}>
                {a}
              </RichBodyText>
            ))}
          </View>
        )}

        {payload.substitution?.length > 0 && (
          <View style={s.section}>
            <RichBodyText style={s.heading}>**Substitution**</RichBodyText>
            {payload.substitution.map((sub, idx) => (
              <RichBodyText key={`sub-${idx}`} style={s.body}>
                {sub}
              </RichBodyText>
            ))}
          </View>
        )}

        {payload.answer && (
          <View style={[s.section, s.answerSection]}>
            <RichBodyText style={s.heading}>**Answer**</RichBodyText>
            <RichBodyText
              style={s.answerText}
            >{`**${payload.answer}**`}</RichBodyText>
          </View>
        )}
      </View>
    </CardShell>
  );
}

function makeStyles(theme: Theme) {
  return StyleSheet.create({
    container: {
      gap: Space.md,
      paddingTop: Space.xs,
    },
    section: {
      gap: Space.xs,
    },
    grid: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: Space.sm,
    },
    gridItem: {
      minWidth: "45%",
      backgroundColor: theme.surfaceAlt,
      paddingHorizontal: Space.sm,
      paddingVertical: Space.xs,
      borderRadius: Radius.md,
    },
    heading: {
      ...Type.body,
      ...Weight.semibold,
      color: theme.textSecondary,
    },
    body: {
      ...Type.body,
      color: theme.text,
    },
    muted: {
      ...Type.caption,
      color: theme.textTertiary,
      fontStyle: "italic",
    },
    answerSection: {
      marginTop: Space.xs,
      paddingTop: Space.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: theme.border,
    },
    answerText: {
      ...Type.body,
      ...Weight.bold,
      color: theme.primary,
    },
  });
}
