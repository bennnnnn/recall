import { ComponentProps, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import type { JobMatch } from "@/lib/api";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export function matchScoreColor(score: number | null, C: Theme): string {
  if (score == null) return C.primary;
  if (score >= 70) return C.primary;
  if (score >= 40) return C.warning;
  return C.textTertiary;
}

export type MetaChip = { icon: ComponentProps<typeof Icon>["name"]; label: string };

/** Wrapping row of icon chips — shared by match cards and the search card. */
export function MetaChipsRow({ chips }: { chips: MetaChip[] }) {
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  if (chips.length === 0) return null;
  return (
    <View style={s.chips}>
      {chips.map((chip) => (
        <View key={`${chip.icon}-${chip.label}`} style={s.chip}>
          <Icon name={chip.icon} size={14} color={C.textTertiary} />
          <Text style={s.chipText} numberOfLines={1}>
            {chip.label}
          </Text>
        </View>
      ))}
    </View>
  );
}

/** Icon chips for location / work mode / salary / experience / posted age. */
export function JobMatchMetaChips({ match }: { match: JobMatch }) {
  const { t } = useTranslation();
  const chips: MetaChip[] = [];
  if (match.location) chips.push({ icon: "location-outline", label: match.location });
  if (match.work_mode)
    chips.push({ icon: "laptop-outline", label: t(`my_job.work_${match.work_mode}`) });
  if (match.salary) chips.push({ icon: "cash-outline", label: match.salary });
  if (match.experience) chips.push({ icon: "bar-chart-outline", label: match.experience });
  if (match.posted_at) chips.push({ icon: "time-outline", label: match.posted_at });
  return <MetaChipsRow chips={chips} />;
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    chips: { flexDirection: "row", flexWrap: "wrap", gap: Space.xs },
    chip: {
      flexDirection: "row",
      alignItems: "center",
      gap: 4,
      minHeight: 28,
      paddingHorizontal: Space.xs,
      borderRadius: Radius.full,
      backgroundColor: C.surfaceAlt,
      maxWidth: "100%",
    },
    chipText: { ...Type.compact, color: C.textSecondary, flexShrink: 1 },
  });
}
