import { ComponentProps, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import type { JobMatch } from "@/lib/api";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { IconSize } from "@/ui/icons/sizes";

export function matchScoreColor(score: number | null, C: Theme): string {
  if (score == null) return C.primary;
  if (score >= 70) return C.primary;
  if (score >= 40) return C.warning;
  return C.textTertiary;
}

export type MetaChip = {
  icon: ComponentProps<typeof Icon>["name"];
  label: string;
  value: string;
};

/** Wrapping row of icon chips — shared by match cards and the search card. */
export function MetaChipsRow({ chips }: { chips: MetaChip[] }) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  if (chips.length === 0) return null;
  return (
    <View style={s.chips}>
      {chips.map((chip) => (
        <View
          key={`${chip.icon}-${chip.label}-${chip.value}`}
          style={s.chip}
          accessibilityLabel={`${chip.label}: ${chip.value}`}
        >
          <Icon name={chip.icon} size={IconSize.xxs} color={C.textTertiary} />
          <Text style={s.chipText} numberOfLines={2}>
            <Text style={s.chipLabel}>{chip.label}: </Text>
            {chip.value}
          </Text>
        </View>
      ))}
    </View>
  );
}

/** Scan-first chips for every verified posting fact. */
export function JobMatchMetaChips({
  match,
  maxSkills = 4,
}: {
  match: JobMatch;
  maxSkills?: number;
}) {
  const { t } = useTranslation();
  const chips: MetaChip[] = [];
  if (match.work_mode)
    chips.push({
      icon: "laptop",
      label: t("my_job.meta_work_mode"),
      value: t(`my_job.work_${match.work_mode}`),
    });
  if (match.location)
    chips.push({
      icon: "map-pin",
      label: t("my_job.meta_location"),
      value: match.location,
    });
  if (match.salary)
    chips.push({
      icon: "banknote",
      label: t("my_job.meta_salary"),
      value: match.salary,
    });
  if (match.experience)
    chips.push({
      icon: "bar-chart",
      label: t("my_job.meta_experience"),
      value: match.experience,
    });
  const skills = match.required_skills.slice(0, maxSkills);
  if (skills.length > 0)
    chips.push({
      icon: "wrench",
      label: t("my_job.meta_skills"),
      value: skills.join(", "),
    });
  if (match.posted_at)
    chips.push({
      icon: "clock",
      label: t("my_job.meta_posted"),
      value: match.posted_at,
    });
  return <MetaChipsRow chips={chips} />;
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    chips: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs },
    chip: {
      flexDirection: "row",
      alignItems: "center",
      gap: Space.xxs,
      minHeight: 28,
      paddingHorizontal: Space.xs,
      borderRadius: Radius.full,
      backgroundColor: C.surfaceAlt,
      maxWidth: "100%",
    },
    chipLabel: { color: C.textTertiary, ...Weight.bold },
    chipText: { ...Type.compact, color: C.textSecondary, flexShrink: 1 },
  });
}
