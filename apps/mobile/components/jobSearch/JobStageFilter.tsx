import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { AppSheet } from "@/components/AppSheet";
import { Icon } from "@/components/Icon";
import { type IoniconName } from "@/lib/icons";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export type JobStageFilterValue =
  "all" | "applied" | "interviewing" | "offer" | "rejected";

type Props = {
  value: JobStageFilterValue;
  counts: Record<JobStageFilterValue, number>;
  onChange: (value: JobStageFilterValue) => void;
};

const OPTIONS: {
  value: JobStageFilterValue;
  labelKey: string;
  icon: IoniconName;
}[] = [
  { value: "all", labelKey: "my_job.tab_all_stages", icon: "layers-outline" },
  {
    value: "applied",
    labelKey: "my_job.tab_applied",
    icon: "checkmark-circle-outline",
  },
  {
    value: "interviewing",
    labelKey: "my_job.tab_interviewing",
    icon: "people-outline",
  },
  { value: "offer", labelKey: "my_job.tab_offers", icon: "trophy-outline" },
  {
    value: "rejected",
    labelKey: "my_job.tab_rejected",
    icon: "remove-circle-outline",
  },
];

export function JobStageFilter({ value, counts, onChange }: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const [open, setOpen] = useState(false);
  const selected =
    OPTIONS.find((option) => option.value === value) ?? OPTIONS[0];
  const selectedLabel = t(selected.labelKey);

  return (
    <>
      <Pressable
        style={({ pressed }) => [s.select, pressed && s.pressed]}
        onPress={() => setOpen(true)}
        accessibilityRole="button"
        accessibilityLabel={`${t("my_job.pipeline")}: ${selectedLabel}`}
        accessibilityState={{ expanded: open }}
      >
        <View style={s.selectCopy}>
          <Text style={s.selectLabel}>{t("my_job.pipeline")}</Text>
          <Text style={s.selectValue}>{selectedLabel}</Text>
        </View>
        {counts[value] > 0 ? (
          <View style={s.countBadge}>
            <Text style={s.countText}>{counts[value]}</Text>
          </View>
        ) : null}
        <Icon name="chevron-down" size={19} color={C.textSecondary} />
      </Pressable>

      <AppSheet
        visible={open}
        onClose={() => setOpen(false)}
        floating
        withHandle
        contentContainerStyle={s.sheet}
      >
        <Text style={s.sheetTitle}>{t("my_job.pipeline")}</Text>
        {OPTIONS.map((option) => {
          const active = option.value === value;
          return (
            <Pressable
              key={option.value}
              style={({ pressed }) => [s.option, pressed && s.optionPressed]}
              onPress={() => {
                onChange(option.value);
                setOpen(false);
              }}
              accessibilityRole="radio"
              accessibilityLabel={t(option.labelKey)}
              accessibilityState={{ selected: active }}
            >
              <Icon
                name={option.icon}
                size={20}
                color={active ? C.primary : C.textSecondary}
              />
              <Text style={[s.optionLabel, active && s.optionLabelActive]}>
                {t(option.labelKey)}
              </Text>
              {counts[option.value] > 0 ? (
                <Text style={s.optionCount}>{counts[option.value]}</Text>
              ) : null}
              {active ? (
                <Icon name="checkmark" size={20} color={C.primary} />
              ) : null}
            </Pressable>
          );
        })}
      </AppSheet>
    </>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    select: {
      minHeight: 58,
      paddingHorizontal: Space.md,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
    },
    selectCopy: { flex: 1 },
    selectLabel: { ...Type.overline, color: C.textTertiary },
    selectValue: { ...Type.label, color: C.text, marginTop: 2 },
    countBadge: {
      minWidth: 24,
      height: 24,
      paddingHorizontal: 7,
      borderRadius: 12,
      backgroundColor: C.primaryLight,
      alignItems: "center",
      justifyContent: "center",
    },
    countText: { ...Type.caption, color: C.primary, fontWeight: "700" },
    sheet: { backgroundColor: C.inputBg, paddingHorizontal: Space.xs },
    sheetTitle: {
      ...Type.navTitle,
      color: C.text,
      textAlign: "center",
      paddingVertical: Space.sm,
    },
    option: {
      minHeight: 56,
      paddingHorizontal: Space.md,
      borderRadius: Radius.lg,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
    },
    optionPressed: { backgroundColor: C.surfaceAlt },
    optionLabel: { ...Type.body, color: C.text, flex: 1 },
    optionLabelActive: { color: C.primary, fontWeight: "700" },
    optionCount: { ...Type.compact, color: C.textTertiary },
    pressed: { opacity: 0.68 },
  });
}
