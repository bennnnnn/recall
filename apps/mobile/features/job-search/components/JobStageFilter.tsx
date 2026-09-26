import { useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/ui/icons/Icon";
import type { IconName } from "@/ui/icons/names";
import { Radius } from "@/lib/radius";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type, Weight } from "@/lib/type";
import { IconSize } from "@/ui/icons/sizes";
import { Menu } from "@/ui/overlay/Menu";

export type JobStageFilterValue =
  "all" | "applied" | "interviewing" | "offer" | "rejected";

type Props = {
  value: JobStageFilterValue;
  counts: Record<JobStageFilterValue, number>;
  active: boolean;
  onOpen: () => void;
  onChange: (value: JobStageFilterValue) => void;
};

const OPTIONS: {
  value: JobStageFilterValue;
  labelKey: string;
  icon: IconName;
}[] = [
  { value: "all", labelKey: "my_job.tab_all_stages", icon: "layers" },
  {
    value: "applied",
    labelKey: "my_job.tab_applied",
    icon: "check-circle",
  },
  {
    value: "interviewing",
    labelKey: "my_job.tab_interviewing",
    icon: "users",
  },
  { value: "offer", labelKey: "my_job.tab_offers", icon: "trophy" },
  {
    value: "rejected",
    labelKey: "my_job.tab_rejected",
    icon: "minus-circle",
  },
];

export function JobStageFilter({
  value,
  counts,
  active,
  onOpen,
  onChange,
}: Props) {
  const { t } = useTranslation();
  const C = useTheme();
  const s = useMemo(() => makeStyles(C), [C]);
  const [open, setOpen] = useState(false);
  const selectRef = useRef<View>(null);
  const selected =
    OPTIONS.find((option) => option.value === value) ?? OPTIONS[0];
  const selectedLabel = t(selected.labelKey);
  const tabLabel = value === "all" ? t("my_job.pipeline") : selectedLabel;
  const tabCount = counts[value];

  const openMenu = () => {
    onOpen();
    setOpen(true);
  };

  return (
    <>
      <Pressable
        ref={selectRef}
        style={({ pressed }) => [
          s.tab,
          active && s.tabActive,
          pressed && s.pressed,
        ]}
        onPress={openMenu}
        accessibilityRole="button"
        accessibilityLabel={`${t("my_job.pipeline")}: ${selectedLabel}`}
        accessibilityState={{ expanded: open, selected: active }}
      >
        <Text style={[s.tabText, active && s.tabTextActive]}>{tabLabel}</Text>
        {tabCount > 0 ? (
          <View style={[s.countBadge, active && s.countBadgeActive]}>
            <Text style={[s.countText, active && s.countTextActive]}>
              {tabCount}
            </Text>
          </View>
        ) : null}
        <Icon
          name="chevron-down"
          size={IconSize.xs}
          color={active ? C.text : C.textSecondary}
        />
      </Pressable>

      <Menu
        visible={open}
        onClose={() => setOpen(false)}
        anchorRef={selectRef}
        selectable
        testID="job-stage-menu"
        items={OPTIONS.map((option) => ({
          key: option.value,
          icon: option.icon,
          label: t(option.labelKey),
          selected: option.value === value,
          trailing: counts[option.value] > 0 ? String(counts[option.value]) : undefined,
          onPress: () => onChange(option.value),
        }))}
      />
    </>
  );
}

function makeStyles(C: Theme) {
  return StyleSheet.create({
    tab: {
      flex: 1,
      minHeight: 44,
      borderRadius: Radius.full,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: Space.sm,
    },
    tabActive: { backgroundColor: C.bg },
    tabText: { ...Type.compact, color: C.textSecondary, ...Weight.semibold },
    tabTextActive: { color: C.text },
    countBadge: {
      minWidth: 24,
      height: 24,
      paddingHorizontal: 7,
      borderRadius: Radius.md,
      backgroundColor: C.surfaceAlt,
      alignItems: "center",
      justifyContent: "center",
    },
    countText: { ...Type.caption, color: C.textSecondary, ...Weight.bold },
    countBadgeActive: { backgroundColor: C.primaryLight },
    countTextActive: { color: C.primary },
    pressed: { opacity: 0.68 },
  });
}
