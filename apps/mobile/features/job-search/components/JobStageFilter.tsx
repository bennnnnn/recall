import { useMemo, useRef, useState } from "react";
import {
  Dimensions,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useTranslation } from "react-i18next";

import { Icon } from "@/components/Icon";
import { type IoniconName } from "@/lib/icons";
import { Radius } from "@/lib/radius";
import { SHADOW_COLOR } from "@/lib/shadow";
import { Space } from "@/lib/space";
import { type Theme, useTheme } from "@/lib/theme";
import { Type } from "@/lib/type";

export type JobStageFilterValue =
  "all" | "applied" | "interviewing" | "offer" | "rejected";

type Props = {
  value: JobStageFilterValue;
  counts: Record<JobStageFilterValue, number>;
  active: boolean;
  onOpen: () => void;
  onChange: (value: JobStageFilterValue) => void;
};

type Anchor = { x: number; y: number; width: number; height: number };

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
  const [anchor, setAnchor] = useState<Anchor>({
    x: Space.md,
    y: 160,
    width: Dimensions.get("window").width - Space.md * 2,
    height: 58,
  });
  const selectRef = useRef<View>(null);
  const selected =
    OPTIONS.find((option) => option.value === value) ?? OPTIONS[0];
  const selectedLabel = t(selected.labelKey);
  const tabLabel = value === "all" ? t("my_job.pipeline") : selectedLabel;
  const tabCount = counts[value];
  const window = Dimensions.get("window");
  const menuHeight = OPTIONS.length * 52 + Space.sm * 2;
  const menuWidth = Math.max(
    220,
    Math.min(anchor.width, window.width - Space.md * 2),
  );
  const menuLeft = Math.max(
    Space.md,
    Math.min(anchor.x, window.width - menuWidth - Space.md),
  );
  const belowTop = anchor.y + anchor.height + Space.xs;
  const menuTop =
    belowTop + menuHeight <= window.height - Space.md
      ? belowTop
      : Math.max(Space.md, anchor.y - menuHeight - Space.xs);

  const openMenu = () => {
    onOpen();
    setOpen(true);
    selectRef.current?.measureInWindow?.((x, y, width, height) => {
      setAnchor({ x, y, width, height });
    });
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
          size={16}
          color={active ? C.text : C.textSecondary}
        />
      </Pressable>

      <Modal
        visible={open}
        transparent
        animationType="fade"
        onRequestClose={() => setOpen(false)}
      >
        <View style={s.overlay}>
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={() => setOpen(false)}
            accessibilityLabel={t("common.close")}
            accessibilityRole="button"
          />
          <View
            style={[s.menu, { top: menuTop, left: menuLeft, width: menuWidth }]}
            accessibilityViewIsModal
          >
            {OPTIONS.map((option) => {
              const active = option.value === value;
              return (
                <Pressable
                  key={option.value}
                  style={({ pressed }) => [
                    s.option,
                    active && s.optionActive,
                    pressed && s.optionPressed,
                  ]}
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
          </View>
        </View>
      </Modal>
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
    tabText: { ...Type.compact, color: C.textSecondary, fontWeight: "600" },
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
    countText: { ...Type.caption, color: C.textSecondary, fontWeight: "700" },
    countBadgeActive: { backgroundColor: C.primaryLight },
    countTextActive: { color: C.primary },
    overlay: { flex: 1 },
    menu: {
      position: "absolute",
      padding: Space.xs,
      borderRadius: Radius.xl,
      backgroundColor: C.surface,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: C.border,
      shadowColor: SHADOW_COLOR,
      shadowOpacity: 0.16,
      shadowRadius: 18,
      shadowOffset: { width: 0, height: 8 },
      elevation: 10,
    },
    option: {
      minHeight: 52,
      paddingHorizontal: Space.md,
      borderRadius: Radius.md,
      flexDirection: "row",
      alignItems: "center",
      gap: Space.sm,
    },
    optionActive: { backgroundColor: C.primaryLight },
    optionPressed: { backgroundColor: C.surfaceAlt },
    optionLabel: { ...Type.body, color: C.text, flex: 1 },
    optionLabelActive: { color: C.primary, fontWeight: "700" },
    optionCount: { ...Type.compact, color: C.textTertiary },
    pressed: { opacity: 0.68 },
  });
}
